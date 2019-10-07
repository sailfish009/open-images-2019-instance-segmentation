import argparse
import os
import os.path as osp
import shutil
import tempfile
import mmcv
import torch
import torch.distributed as dist
from mmcv.runner import load_checkpoint, get_dist_info
from mmcv.parallel import MMDataParallel, MMDistributedDataParallel
from mmdet.apis import init_dist
from mmdet.core import results2json, coco_eval
from mmdet.datasets import build_dataloader, get_dataset
from mmdet.models import build_detector


def single_gpu_test(model, data_loader, show=False):
  model.eval()
  results = []
  dataset = data_loader.dataset
  prog_bar = mmcv.ProgressBar(len(dataset))
  for i, data in enumerate(data_loader):
    with torch.no_grad():
      if i % 200 == 0: print(f"  {i}")
      result = model(return_loss=False, rescale=not show, **data)
    results.append(result)
    if show:
      model.module.show_result(data, result, dataset.img_norm_cfg)
    batch_size = data['img'][0].size(0)
    for _ in range(batch_size):
      prog_bar.update()
  return results


def multi_gpu_test(model, data_loader, tmpdir=None):
  model.eval()
  results = []
  dataset = data_loader.dataset
  rank, world_size = get_dist_info()
  if rank == 0:
    prog_bar = mmcv.ProgressBar(len(dataset))
  for i, data in enumerate(data_loader):
    with torch.no_grad():
      result = model(return_loss=False, rescale=True, **data)
    results.append(result)
    if rank == 0:
      batch_size = data['img'][0].size(0)
      for _ in range(batch_size * world_size):
        prog_bar.update()
  # collect results from all ranks
  results = collect_results(results, len(dataset), tmpdir)
  return results


def collect_results(result_part, size, tmpdir=None):
  rank, world_size = get_dist_info()
  # create a tmp dir if it is not specified
  if tmpdir is None:
    MAX_LEN = 512
    # 32 is whitespace
    dir_tensor = torch.full((MAX_LEN,),
                            32,
                            dtype=torch.uint8,
                            device='cuda')
    if rank == 0:
      tmpdir = tempfile.mkdtemp()
      tmpdir = torch.tensor(
        bytearray(tmpdir.encode()), dtype=torch.uint8, device='cuda')
      dir_tensor[:len(tmpdir)] = tmpdir
    dist.broadcast(dir_tensor, 0)
    tmpdir = dir_tensor.cpu().numpy().tobytes().decode().rstrip()
  else:
    mmcv.mkdir_or_exist(tmpdir)
  # dump the part result to the dir
  mmcv.dump(result_part, osp.join(tmpdir, 'part_{}.pkl'.format(rank)))
  dist.barrier()
  # collect all parts
  if rank != 0:
    return None
  else:
    # load results of all parts from tmp dir
    part_list = []
    for i in range(world_size):
      part_file = osp.join(tmpdir, 'part_{}.pkl'.format(i))
      part_list.append(mmcv.load(part_file))
    # sort the results
    ordered_results = []
    for res in zip(*part_list):
      ordered_results.extend(list(res))
    # the dataloader may pad some samples
    ordered_results = ordered_results[:size]
    # remove tmp dir
    shutil.rmtree(tmpdir)
    return ordered_results


def parse_args():
  parser = argparse.ArgumentParser(description='MMDet test detector')
  parser.add_argument('config', help='test config file path')
  parser.add_argument('checkpoint', help='checkpoint file')
  parser.add_argument('ann_file')
  parser.add_argument('--thres', type=float, default=0.05)
  parser.add_argument('--max_per_img', type=int, default=100)
  parser.add_argument('--out', help='output result file')
  parser.add_argument('--nms_type',default='nms')
  parser.add_argument(
    '--eval',
    type=str,
    nargs='+',
    choices=['proposal', 'proposal_fast', 'bbox', 'segm', 'keypoints'],
    help='eval types')
  parser.add_argument('--show', action='store_true', help='show results')
  parser.add_argument('--tmpdir', help='tmp dir for writing some results')
  parser.add_argument(
    '--launcher',
    choices=['none', 'pytorch', 'slurm', 'mpi'],
    default='none',
    help='job launcher')
  parser.add_argument('--local_rank', type=int, default=0)
  args = parser.parse_args()
  if 'LOCAL_RANK' not in os.environ:
    os.environ['LOCAL_RANK'] = str(args.local_rank)
  return args


def main():
  args = parse_args()
  if args.out is not None and not args.out.endswith(('.pkl', '.pickle')):
    raise ValueError('The output file must be a pkl file.')
  cfg = mmcv.Config.fromfile(args.config)
  # set cudnn_benchmark
  if cfg.get('cudnn_benchmark', False):
    torch.backends.cudnn.benchmark = True
  cfg.model.pretrained = None
  cfg.data.test.test_mode = True
  # init distributed env first, since logger depends on the dist info.
  if args.launcher == 'none':
    distributed = False
  else:
    distributed = True
    init_dist(args.launcher, **cfg.dist_params)
  # build the dataloader
  # TODO: support multiple images per gpu (only minor changes are needed)
  dataset_type = 'OIDSegDataset'
  data_root = 'gs://oid2019/data/'
  img_norm_cfg = dict(
    mean=[123.675, 116.28, 103.53], std=[58.395, 57.12, 57.375], to_rgb=True)
  dataset = get_dataset(
    dict(
      type=dataset_type,
      ann_file='/home/bo_liu/' + args.ann_file,
      img_prefix=data_root + ('val/' if args.ann_file == 'seg_val_2844_ann.pkl' else 'OD_test/'),
      img_scale=(1333, 800),
      img_norm_cfg=img_norm_cfg,
      size_divisor=32,
      flip_ratio=0,
      with_mask=True,
      with_label=False,
      test_mode=True)
  )

  data_loader = build_dataloader(
    dataset,
    imgs_per_gpu=1,
    workers_per_gpu=cfg.data.workers_per_gpu,
    dist=distributed,
    shuffle=False)
  # build the model and load checkpoint
  test_cfg = mmcv.ConfigDict(dict(
    rpn=dict(
      nms_across_levels=False,
      nms_pre=1000,
      nms_post=1000,
      max_num=1000,
      nms_thr=0.7,
      min_bbox_size=0),
    rcnn=dict(
      score_thr=args.thres,
      # score_thr=0.0,
      nms=dict(type=args.nms_type, iou_thr=0.5),
      max_per_img=args.max_per_img,
      mask_thr_binary=0.5),
    keep_all_stages=False))
  model = build_detector(cfg.model, train_cfg=None, test_cfg=test_cfg)
  checkpoint = load_checkpoint(model, args.checkpoint, map_location='cpu')
  # old versions did not save class info in checkpoints, this walkaround is
  # for backward compatibility
  if 'CLASSES' in checkpoint['meta']:
    model.CLASSES = checkpoint['meta']['CLASSES']
  else:
    model.CLASSES = dataset.CLASSES
  if not distributed:
    model = MMDataParallel(model, device_ids=[0])
    outputs = single_gpu_test(model, data_loader, args.show)
  else:
    model = MMDistributedDataParallel(model.cuda())
    outputs = multi_gpu_test(model, data_loader, args.tmpdir)
  rank, _ = get_dist_info()
  if args.out and rank == 0:
    print('writing results to {}'.format(args.out))
    mmcv.dump(outputs, args.out)
    eval_types = args.eval
    if eval_types:
      print('Starting evaluate {}'.format(' and '.join(eval_types)))
      if eval_types == ['proposal_fast']:
        result_file = args.out
        coco_eval(result_file, eval_types, dataset.coco)
      else:
        if not isinstance(outputs[0], dict):
          result_file = args.out + '.json'
          results2json(dataset, outputs, result_file)
          coco_eval(result_file, eval_types, dataset.coco)
        else:
          for name in outputs[0]:
            print('Evaluating {}'.format(name))
            outputs_ = [out[name] for out in outputs]
            result_file = args.out + '.{}.json'.format(name)
            results2json(dataset, outputs_, result_file)
            coco_eval(result_file, eval_types, dataset.coco)

if __name__ == '__main__':
    main()            
