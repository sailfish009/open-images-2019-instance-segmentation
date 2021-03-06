import argparse
import os
import os.path as osp
import shutil
import tempfile

import pandas as pd
from tqdm import tqdm

import mmcv
import torch
import torch.distributed as dist
from mmcv.runner import load_checkpoint, get_dist_info
from mmcv.parallel import MMDataParallel, MMDistributedDataParallel

from mmdet.apis import init_dist
from mmdet.core import results2json, coco_eval
from mmdet.datasets import build_dataloader, get_dataset
from mmdet.models import build_detector


CLASSES = (
'/m/0242l', '/m/03120', '/m/0h8l4fh', '/m/0167gd', '/m/01j51', '/m/029b3', '/m/02zt3', '/m/0kmg4',
'/m/0174k2', '/m/01k6s3', '/m/029bxz', '/m/02pjr4', '/m/02wv84t', '/m/02x984l', '/m/03s_tn', '/m/040b_t',
'/m/04169hn', '/m/063rgb', '/m/07xyvk', '/m/0fx9l', '/m/0llzx', '/m/03ldnb', '/m/0130jx', '/m/01vbnl', 
'/m/02f9f_', '/m/02jz0l', '/m/03dnzn', '/m/09g1w', '/m/01lsmm', '/m/01n5jq', '/m/025dyy', '/m/02d9qx',
'/m/03m3vtv', '/m/04zwwv', '/m/05gqfk', '/m/09gtd', '/m/0frqm', '/m/0k1tl', '/m/02w3r3', '/m/034c16',
'/m/02d1br', '/m/02pdsw', '/m/03v5tg', '/m/07v9_z', '/m/01_5g', '/m/01fh4r', '/m/02jvh9', '/m/02p5f1q',
'/m/02x8cch', '/m/03q5c7', '/m/04dr76w', '/m/04kkgm', '/m/050gv4', '/m/054fyh', '/m/058qzx', '/m/08hvt4',
'/m/099ssp', '/m/09tvcd', '/m/0cmx8', '/m/0dt3t', '/m/0h8n27j', '/m/0h8n6ft', '/m/04v6l4', '/m/084rd',
'/m/02tsc9', '/m/03y6mg', '/m/0h8ntjv', '/m/03tw93', '/m/0b3fp9', '/m/0bt_c3', '/m/01mzpv', '/m/01s105',
'/m/01y9k5', '/m/03m3pdh', '/m/0703r8', '/m/02z51p', '/m/03__z0', '/m/061hd_', '/m/026qbn5', '/m/047j0r',
'/m/078n6m', '/m/0h8n5zk', '/m/05kyg_', '/m/0642b4', '/m/0cvnqh', '/m/0fqfqc', '/m/0fqt361', '/m/0gjbg72',
'/m/0h8mzrc', '/m/04y4h8h', '/m/0h8n6f9', '/m/01jfsr', '/m/046dlr', '/m/06_72j', '/m/02s195', '/m/031b6r',
'/m/03rszm', '/m/054_l', '/m/0152hh', '/m/04yqq2', '/m/01yx86', '/m/06z37_', '/m/0c06p', '/m/0dtln', '/m/0fm3zh',
'/m/0162_1', '/m/01gllr', '/m/01j61q', '/m/015qff', '/m/01knjb', '/m/02pv19', '/m/01pns0', '/m/0220r2',
'/m/033rq4', '/m/04h7h', '/m/079cl', '/m/0d5gx', '/m/01fdzj', '/m/03jm5', '/m/021sj1', '/m/0crjs', '/m/0b_rs',
'/m/04yx4', '/m/03bt1vf', '/m/01bl7v', '/m/05r655', '/m/01b9xk', '/m/02y6n', '/m/01dwsz', '/m/01dwwc', '/m/01j3zr',
'/m/01f91_', '/m/01hrv5', '/m/01tcjp', '/m/021mn', '/m/0cxn2', '/m/0fszt', '/m/0gm28', '/m/02g30s', '/m/014j1m',
'/m/0388q', '/m/043nyj', '/m/061_f', '/m/07fbm7', '/m/07j87', '/m/09k_b', '/m/09qck', '/m/0cyhj_', '/m/0dj6p',
'/m/0fldg', '/m/0fp6w', '/m/0hqkz', '/m/0jwn_', '/m/0kpqd', '/m/033cnk', '/m/01fb_0', '/m/09728', '/m/0jy4k',
'/m/015wgc', '/m/02zvsm', '/m/052sf', '/m/05z55', '/m/0663v', '/m/0_cp5', '/m/0cjq5', '/m/0ll1f78', '/m/0n28_',
'/m/07crc', '/m/015x4r', '/m/015x5n', '/m/047v4b', '/m/05vtc', '/m/0cjs7', '/m/05zsy', '/m/027pcv', '/m/0fbw6',
'/m/0fj52s', '/m/0grw1', '/m/0hkxq', '/m/0jg57', '/m/02cvgx', '/m/0fz0h', '/m/0cdn1', '/m/06pcq', '/m/07030',
'/m/03fp41', '/m/025nd', '/m/0cdl1', '/m/0cffdh', '/m/0mw_6', '/m/04gth', '/m/06m11', '/m/0ftb8', '/m/0jqgx',
'/m/012n7d', '/m/018p4k', '/m/0199g', '/m/01bjv', '/m/01x3jk', '/m/0323sq', '/m/04_sv', '/m/076bq', '/m/07cmd',
'/m/07jdr', '/m/07r04', '/m/01lcw4', '/m/0h2r6', '/m/0pg52', '/m/0qmmr', '/m/01btn', '/m/02068x', '/m/0ph39',
'/m/01xs3r', '/m/09ct_', '/m/0cmf2', '/m/09rvcxw', '/m/01bfm9', '/m/01d40f', '/m/01gkx_', '/m/01gmv2', '/m/01krhy',
'/m/01n4qj', '/m/01xygc', '/m/01xyhv', '/m/025rp__', '/m/02fq_6', '/m/02jfl0', '/m/02wbtzl', '/m/02h19r', '/m/01cmb2',
'/m/032b3c', '/m/03grzl', '/m/0176mf', '/m/01llwg', '/m/01nq26', '/m/01r546', '/m/01rkbr', '/m/0gjkl', '/m/0hnnb',
'/m/0nl46', '/m/04tn4x', '/m/0fly7', '/m/02p3w7d', '/m/01b638', '/m/06k2mb', '/m/03nfch', '/m/0h8mhzd', '/m/01940j',
'/m/01s55n', '/m/0584n8', '/m/080hkjn', '/m/03p3bw', '/m/07qxg_', '/m/01dy8n', '/m/01f8m5', '/m/05n4y', '/m/05z6w',
'/m/06j2d', '/m/09b5t', '/m/09csl', '/m/09d5_', '/m/09ddx', '/m/0ccs93', '/m/0dbvp', '/m/0dftk', '/m/0f6wt', '/m/0gv1x',
'/m/0h23m', '/m/0jly1', '/m/0175cv', '/m/019h78', '/m/01h8tj', '/m/0d8zb', '/m/01h3n', '/m/0gj37', '/m/0_k2', '/m/0cydv',
'/m/0cyf8', '/m/0ft9s', '/m/09kmb', '/m/0f9_l', '/m/01h44', '/m/01dxs', '/m/0633h', '/m/01yrx', '/m/0306r', '/m/0449p',
'/m/04g2r', '/m/07dm6', '/m/096mb', '/m/0bt9lr', '/m/0c29q', '/m/0cd4d', '/m/0cn6p', '/m/0dq75', '/m/01x_v', '/m/01xq0k1',
'/m/03bk1', '/m/03d443', '/m/03fwl', '/m/03k3r', '/m/03qrc', '/m/04c0y', '/m/04rmv', '/m/068zj', '/m/06mf6', '/m/071qp',
'/m/07bgp', '/m/0898b', '/m/08pbxl', '/m/09kx5', '/m/0bwd_0j', '/m/0c568', '/m/0cnyhnx', '/m/0czz2', '/m/0dbzx',
'/m/02hj4', '/m/084zz', '/m/0gd36', '/m/02l8p9', '/m/0pcr', '/m/029tx', '/m/04m9y', '/m/078jl', '/m/011k07', '/m/0120dh',
'/m/09f_2', '/m/09ld4', '/m/03fj2', '/m/0by6g', '/m/0nybt', '/m/017ftj', '/m/02_n6y', '/m/05441v', '/m/0jyfg',
'/m/02lbcq', '/m/013y1f', '/m/01xqw', '/m/026t6', '/m/0319l', '/m/0342h', '/m/03m5k', '/m/03q5t', '/m/057cc', '/m/05kms',
'/m/05r5c', '/m/06ncr', '/m/07c6l', '/m/07gql', '/m/07y_7', '/m/0l14j_', '/m/0mkg', '/m/014y4n', '/m/01226z', '/m/02ctlc',
'/m/02rgn06', '/m/05ctyq', '/m/0wdt60w', '/m/019w40', '/m/03g8mr', '/m/0420v5', '/m/044r5d', '/m/054xkw', '/m/057p5t',
'/m/06__v', '/m/06_fw', '/m/071p9', '/m/04h8sr', '/m/03kt2w', '/m/030610', '/m/076lb9', '/m/0cyfs', '/m/0h8my_4',
'/m/05_5p_0', '/m/04p0qw', '/m/02jnhm', '/m/02zn6n', '/m/07kng9', '/m/0bjyj5', '/m/0d20w4', '/m/012w5l', '/m/01bms0',
'/m/01j5ks', '/m/01kb5b', '/m/04vv5k', '/m/05bm6', '/m/073bxn', '/m/07dd4', '/m/0dv5r', '/m/0hdln', '/m/0lt4_',
'/m/01g3x7', '/m/020kz', '/m/02gzp', '/m/04ctx', '/m/06c54', '/m/06nrc', '/m/0gxl3', '/m/06y5r', '/m/04ylt', '/m/01b7fy',
'/m/01c648', '/m/01m2v', '/m/01m4t', '/m/020lf', '/m/02522', '/m/03bbps', '/m/03jbxj', '/m/07c52', '/m/050k8', '/m/0h8lkj8',
'/m/0bh9flk', '/m/0hg7b', '/m/01599', '/m/024g6', '/m/02vqfm', '/m/01z1kdw', '/m/07clx', '/m/081qc', '/m/01bqk0',
'/m/03c7gz', '/m/02dgv', '/m/0d4v4', '/m/01lynh', '/m/04m6gz', '/m/014sv8', '/m/016m2d', '/m/04hgtk', '/m/0dzct',
'/m/0283dt1', '/m/039xj_', '/m/0k0pj', '/m/03q69', '/m/0k65p', '/m/031n1', '/m/0dzf4', '/m/035r7c', '/m/015h_t',
'/m/01jfm_', '/m/083wq', '/m/0dkzw', '/m/0h9mv', '/m/0djtd'
)


def single_gpu_test(model, data_loader, show=False):
    model.eval()
    results = []
    dataset = data_loader.dataset
    prog_bar = mmcv.ProgressBar(len(dataset))
    for i, data in enumerate(data_loader):
        with torch.no_grad():
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
        dir_tensor = torch.full((MAX_LEN, ),
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
    parser.add_argument('--out', help='output result file')
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
    dataset = get_dataset(cfg.data.test)
    data_loader = build_dataloader(
        dataset,
        imgs_per_gpu=1,
        workers_per_gpu=cfg.data.workers_per_gpu,
        dist=distributed,
        shuffle=False)

    # build the model and load checkpoint
    model = build_detector(cfg.model, train_cfg=None, test_cfg=cfg.test_cfg)
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
        print('\nwriting results to {}'.format(args.out))
        mmcv.dump(outputs, args.out)

        dataset.CLASSES = CLASSES

        data_list = []
        for i in tqdm(range(len(dataset))): 
            img_id = dataset.img_infos[i]['filename'].split('.')[0]
            w = dataset.img_infos[i]['width']
            h = dataset.img_infos[i]['height']
            for l in range(len(dataset.CLASSES)):
                l_name = dataset.CLASSES[l] 
                for b in outputs[i][l]: 
                    if len(b)>0: 
                        data_list.append((img_id, l_name, b[-1], b[0]/w, b[1]/h, b[2]/w, b[3]/h))
        data_df = pd.DataFrame(data_list, columns =['ImageID', 'LabelName', 'Score', 'XMin', 'YMin', 'XMax', 'YMax'])
        data_df.to_csv(args.out.split('.pkl')[0]+'.csv', index=False)



if __name__ == '__main__':
    main()
