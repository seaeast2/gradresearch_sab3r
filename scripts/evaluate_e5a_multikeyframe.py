#!/usr/bin/env python3
"""Evaluate B0-B3 on a multi-Keyframe Replica scene with one common B0 Sim(3)."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, deque
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

from build_e3_regions import normals_and_spacing
from evaluate_e5_gt import apply_sim3, backproject, fit_umeyama, source_depth_grid
from refine_e4a_temporal_regions import fit_plane_ransac


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def mutual_matches(left, right, radius):
    flat_a = np.flatnonzero(left["valid"].ravel())
    flat_b = np.flatnonzero(right["valid"].ravel())
    pa = left["data"]["point_world"].reshape(-1, 3)[flat_a].astype(np.float64)
    pb = right["data"]["point_world"].reshape(-1, 3)[flat_b].astype(np.float64)
    dab, nab = cKDTree(pb).query(pa, k=1, workers=-1)
    _dba, nba = cKDTree(pa).query(pb, k=1, workers=-1)
    mutual = (dab <= radius) & (nba[nab] == np.arange(len(pa)))
    pix_a = flat_a[mutual]
    pix_b = flat_b[nab[mutual]]
    return pix_a, pix_b, dab[mutual]


def correspondence_links(frames, region_ids, radius, spacing, min_corr, min_overlap, min_region_pixels):
    """One-to-one geometry-only region matching; returns score evidence per local region."""
    per_region: dict[tuple[int, int], dict] = {}
    links = []
    for left, right in zip(frames, frames[1:]):
        pix_a, pix_b, distances = mutual_matches(left, right, radius)
        ids_a = region_ids[left["ordinal"]].ravel()[pix_a]
        ids_b = region_ids[right["ordinal"]].ravel()[pix_b]
        keep = (ids_a > 0) & (ids_b > 0)
        ids_a, ids_b, distances = ids_a[keep], ids_b[keep], distances[keep]
        counts = Counter(zip(ids_a.tolist(), ids_b.tolist()))
        sizes_a = np.bincount(region_ids[left["ordinal"]].ravel())
        sizes_b = np.bincount(region_ids[right["ordinal"]].ravel())
        regs_a = [int(i) for i in np.flatnonzero(sizes_a >= min_region_pixels) if i > 0]
        regs_b = [int(i) for i in np.flatnonzero(sizes_b >= min_region_pixels) if i > 0]
        index_a, index_b = {x: i for i, x in enumerate(regs_a)}, {x: i for i, x in enumerate(regs_b)}
        score = np.zeros((len(regs_a), len(regs_b)), dtype=np.float64)
        details = {}
        for (ra, rb), count in counts.items():
            if ra not in index_a or rb not in index_b:
                continue
            size_a = int(sizes_a[ra])
            size_b = int(sizes_b[rb])
            overlap = min(count / max(size_a, 1), count / max(size_b, 1))
            score[index_a[ra], index_b[rb]] = overlap
            selected = (ids_a == ra) & (ids_b == rb)
            vals = distances[selected]
            details[(ra, rb)] = {
                "count": int(count), "overlap": float(overlap),
                "p90_spacing_ratio": float(np.percentile(vals, 90) / max(spacing, 1e-12)) if vals.size else 0.0,
                "pixel_count": [size_a, size_b],
            }
        cost = 1.0 - score
        for (ra, rb), d in details.items():
            if d["count"] < min_corr or d["overlap"] < min_overlap:
                cost[index_a[ra], index_b[rb]] = 1e6
        accepted = []
        if cost.size:
            rows, cols = linear_sum_assignment(cost)
            for i, j in zip(rows.tolist(), cols.tolist()):
                ra, rb = regs_a[i], regs_b[j]
                d = details.get((ra, rb))
                if d and cost[i, j] < 1e5:
                    accepted.append((ra, rb, d))
        for ra, rb, d in accepted:
            link = {
                "from_keyframe_ordinal": left["ordinal"], "to_keyframe_ordinal": right["ordinal"],
                "from_local_region_id": int(ra), "to_local_region_id": int(rb), **d,
            }
            links.append(link)
            for key in ((left["ordinal"], ra), (right["ordinal"], rb)):
                entry = per_region.setdefault(key, {"max_p90_spacing_ratio": 0.0, "correspondence_count": 0, "links": []})
                entry["max_p90_spacing_ratio"] = max(entry["max_p90_spacing_ratio"], d["p90_spacing_ratio"])
                entry["correspondence_count"] += d["count"]
                entry["links"].append(link)
    return per_region, links


def geometry_only_regions(points, valid, cfg):
    """Seed-anchored planar region growing without semantic labels."""
    labels = np.zeros(valid.shape, dtype=np.uint8)
    normals, spacing, _fallback = normals_and_spacing(points, labels, valid)
    h, w = valid.shape
    output = np.zeros((h, w), dtype=np.int32)
    next_id = 0
    factor = float(cfg["max_neighbor_distance_over_local_spacing"])
    cosine = float(np.cos(np.deg2rad(cfg["max_seed_normal_angle_degrees"])))
    plane_factor = float(cfg["max_seed_plane_offset_over_local_spacing"])
    for sy in range(h):
        for sx in range(w):
            if not valid[sy, sx] or output[sy, sx] != 0:
                continue
            next_id += 1
            output[sy, sx] = next_id
            seed_point = points[sy, sx].astype(np.float64)
            seed_normal = normals[sy, sx].astype(np.float64)
            if not np.isfinite(seed_normal).all():
                continue
            stack = deque([(sy, sx)])
            max_seed_offset = plane_factor * max(float(spacing[sy, sx]), 1e-8)
            while stack:
                cy, cx = stack.pop()
                for ny, nx in ((cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)):
                    if ny < 0 or nx < 0 or ny >= h or nx >= w or not valid[ny,nx] or output[ny,nx] != 0:
                        continue
                    delta = points[ny,nx].astype(np.float64) - points[cy,cx].astype(np.float64)
                    if not np.isfinite(delta).all() or np.linalg.norm(delta) > factor * min(float(spacing[cy,cx]), float(spacing[ny,nx])):
                        continue
                    normal = normals[ny,nx]
                    if not np.isfinite(normal).all() or abs(float(np.dot(seed_normal, normal))) < cosine:
                        continue
                    if abs(float(np.dot(seed_normal, points[ny,nx].astype(np.float64)-seed_point))) > max_seed_offset:
                        continue
                    output[ny,nx] = next_id
                    stack.append((ny,nx))
    return output


def refine_frame_local(frame, region_ids, per_region, spacing, config, require_semantics):
    """Same bounded ray-depth optimizer for one observation per Region."""
    elig = config["eligibility"]
    min_pixels = int(elig["minimum_total_region_pixels"])
    min_corr = int(elig["minimum_mutual_correspondences"])
    min_obs = int(elig["minimum_observations"])
    max_planarity = float(elig["maximum_pca_smallest_eigenvalue_ratio"])
    min_inliers = float(elig["minimum_ransac_inlier_fraction"])
    candidate_labels = set(elig["candidate_semantic_labels"])
    threshold = float(config["frozen_error_threshold_spacing_ratio"])
    plane_threshold = float(config["plane_fit"]["inlier_distance_over_global_spacing"]) * spacing
    max_delta = float(config["refinement"]["maximum_radial_displacement_over_global_spacing"]) * spacing
    huber_delta = float(config["refinement"]["huber_delta_over_global_spacing"]) * spacing
    prior = float(config["refinement"]["displacement_prior_lambda"])
    boundary = int(config["refinement"]["boundary_freeze_pixels"])
    conf_all = frame["data"]["confidence_avg"][frame["valid"]]
    conf_scale = max(float(np.median(conf_all)) if conf_all.size else 1.0, 1e-6)
    result_points = frame["data"]["point_world"].astype(np.float32).copy()
    modified = np.zeros(frame["valid"].shape, dtype=bool)
    candidate_rows = []
    for rid in np.unique(region_ids[region_ids > 0]):
        mask = (region_ids == rid) & frame["valid"]
        values = frame["data"]["point_world"][mask].astype(np.float64)
        evidence = per_region.get((frame["ordinal"], int(rid)), {})
        score = evidence.get("max_p90_spacing_ratio")
        corr_count = evidence.get("correspondence_count", 0)
        label_id = int(np.bincount(frame["labels"][mask]).argmax()) if mask.any() else -1
        label = frame["label_names"][label_id] if 0 <= label_id < len(frame["label_names"]) else "unknown"
        row = {"keyframe_ordinal": frame["ordinal"], "frame_id": frame["frame_id"], "local_region_id": int(rid),
               "semantic_label": label if require_semantics else "geometry_only", "pixel_count": int(mask.sum()),
               "temporal_p90_error_score_spacing_ratio": score, "mutual_correspondence_count": int(corr_count),
               "status": "not_selected", "reason": []}
        reasons = []
        if require_semantics and label not in candidate_labels:
            reasons.append("semantic_label_not_in_planar_candidates")
        if score is None or score < threshold:
            reasons.append("temporal_error_score_below_frozen_threshold")
        if evidence.get("observation_count", min_obs) < min_obs:
            reasons.append("insufficient_keyframe_observations")
        if int(mask.sum()) < min_pixels:
            reasons.append("below_minimum_region_pixels")
        if corr_count < min_corr:
            reasons.append("below_minimum_mutual_correspondences")
        if reasons:
            row["reason"] = reasons
            candidate_rows.append(row)
            continue
        if len(values) < 3:
            row.update(status="ineligible", reason=["too_few_points"])
            candidate_rows.append(row)
            continue
        center = values.mean(axis=0)
        eig = np.maximum(np.linalg.eigvalsh((values-center).T @ (values-center) / len(values)), 0)
        ratio = float(eig[0] / max(eig.sum(), 1e-12))
        row["pca_planarity_ratio"] = ratio
        if ratio > max_planarity:
            row.update(status="ineligible", reason=["pca_planarity_exceeded"])
            candidate_rows.append(row)
            continue
        plane, inliers = fit_plane_ransac(values, plane_threshold, int(config["plane_fit"]["iterations"]), int(config["plane_fit"]["seed"]) + int(rid))
        if plane is None or float(inliers.mean()) < min_inliers:
            row.update(status="ineligible", reason=["ransac_inlier_fraction_below_limit"])
            candidate_rows.append(row)
            continue
        normal, offset = plane
        before_rmse = float(np.sqrt(np.mean((values @ normal + offset) ** 2)))
        interior = ndimage.binary_erosion(mask, structure=np.ones((3,3), dtype=bool), iterations=boundary, border_value=0) if boundary else mask
        yy, xx = np.where(interior)
        if not len(yy):
            row.update(status="ineligible", reason=["no_region_interior"])
            candidate_rows.append(row)
            continue
        original = frame["data"]["point_world"].astype(np.float64)
        center_cam = frame["data"]["pose_sim3_raw"].astype(np.float64).reshape(-1)[:3]
        rel = original[yy,xx]-center_cam
        depth0 = np.linalg.norm(rel,axis=-1)
        rays = rel/np.maximum(depth0[:,None],1e-12)
        a = rays@normal; b=float(np.dot(normal,center_cam)+offset)
        good=np.isfinite(a)&np.isfinite(depth0)&(np.abs(a)>=0.1)&(depth0>1e-6)
        yy,xx,rays,depth0,a=yy[good],xx[good],rays[good],depth0[good],a[good]
        if not len(yy):
            row.update(status="ineligible",reason=["rays_parallel_to_plane"]); candidate_rows.append(row); continue
        conf=frame["data"]["confidence_avg"][yy,xx].astype(np.float64)
        weights=np.clip(conf/conf_scale,0.1,10.0); depth=depth0.copy()
        for _ in range(8):
            residual=a*depth+b; robust=np.minimum(1.0,huber_delta/np.maximum(np.abs(residual),1e-12))
            depth=np.clip((weights*robust*a*(-b)+prior*depth0)/np.maximum(weights*robust*a*a+prior,1e-12),depth0-max_delta,depth0+max_delta)
        new=center_cam+rays*depth[:,None]
        displacement=np.linalg.norm(new-original[yy,xx],axis=-1); moved=displacement>1e-6
        result_points[yy[moved],xx[moved]]=new[moved].astype(np.float32); modified[yy[moved],xx[moved]]=True
        full=result_points[mask].astype(np.float64)
        after_rmse=float(np.sqrt(np.mean((full@normal+offset)**2)))
        improvement=(before_rmse-after_rmse)/max(before_rmse,1e-12)
        if improvement < float(config["refinement"]["minimum_relative_plane_rmse_improvement"]):
            result_points[mask]=frame["data"]["point_world"][mask]; modified[mask]=False
            row.update(status="rejected_and_rolled_back",reason=["plane_rmse_improvement_below_limit"])
        else:
            row.update(status="applied",reason=[],modified_pixel_count=int(moved.sum()),
                       max_displacement_world_units=float(displacement.max()),
                       plane_rmse_before_world_units=before_rmse,plane_rmse_after_world_units=after_rmse,
                       relative_plane_rmse_improvement=improvement)
        candidate_rows.append(row)
    return result_points, modified, candidate_rows


def summarize(errors, mask, threshold):
    vals=errors[mask & np.isfinite(errors)]
    if not vals.size:
        return {"point_count":0,"rmse_m":None,"mean_m":None,"median_m":None,"p95_m":None,"outlier_rate_over_threshold":None,"same_pixel_fscore":None}
    within=vals<=threshold
    return {"point_count":int(len(vals)),"rmse_m":float(np.sqrt(np.mean(vals**2))),"mean_m":float(vals.mean()),
            "median_m":float(np.median(vals)),"p95_m":float(np.percentile(vals,95)),
            "outlier_rate_over_threshold":float(np.mean(~within)),"same_pixel_fscore":float(within.mean())}


def normals(points, valid):
    h,w=valid.shape
    out=np.full((h,w,3),np.nan,dtype=np.float32)
    dx=points[1:-1,2:]-points[1:-1,:-2]
    dy=points[2:,1:-1]-points[:-2,1:-1]
    n=np.cross(dx,dy); mag=np.linalg.norm(n,axis=-1)
    ok=valid[1:-1,1:-1]&valid[1:-1,2:]&valid[1:-1,:-2]&valid[2:,1:-1]&valid[:-2,1:-1]&(mag>1e-8)
    block=out[1:-1,1:-1]; block[ok]=n[ok]/mag[ok,None]
    return out


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1a-artifacts",type=Path,required=True)
    parser.add_argument("--e2a-artifacts",type=Path,required=True)
    parser.add_argument("--e3a-artifacts",type=Path,required=True)
    parser.add_argument("--e4a-artifacts",type=Path,required=True)
    parser.add_argument("--source-manifest",type=Path,required=True)
    parser.add_argument("--camera-params",type=Path,required=True)
    parser.add_argument("--depth-root",type=Path,required=True)
    parser.add_argument("--trajectory",type=Path,required=True)
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()): parser.error(f"refusing to mix artifacts: {args.output}")
    start=time.perf_counter()
    e1,e2,e3,e4=(p.resolve() for p in (args.e1a_artifacts,args.e2a_artifacts,args.e3a_artifacts,args.e4a_artifacts))
    config=json.loads(args.config.read_text()); exp=json.loads((e1/'pointmaps/export_manifest.json').read_text())
    tags=json.loads((e2/'keyframes_manifest.json').read_text()); temporal=json.loads((e3/'temporal_regions.json').read_text())
    refined_summary=json.loads((e4/'refinement_summary.json').read_text())
    optimizer_config=refined_summary['config']
    source_manifest=json.loads(args.source_manifest.read_text()); cam=json.loads(args.camera_params.read_text())['camera']
    traj=np.loadtxt(args.trajectory,dtype=np.float64).reshape(-1,4,4)
    if tags['source_e1a_export_manifest_sha256']!=sha256(e1/'pointmaps/export_manifest.json'):
        parser.error('E2a/E1a source manifest hash mismatch')
    if temporal['source_manifests']['e1a_sha256']!=sha256(e1/'pointmaps/export_manifest.json') or temporal['source_manifests']['e2a_sha256']!=sha256(e2/'keyframes_manifest.json'):
        parser.error('E3a source manifest hashes mismatch')
    if refined_summary['sources']['e3a_temporal_regions_sha256']!=sha256(e3/'temporal_regions.json'):
        parser.error('E4a does not reference the supplied E3a results')
    args.output.mkdir(parents=True,exist_ok=True)
    region_archive=np.load(e3/'region_masks.npz',allow_pickle=False)
    frames=[]; records=[]
    for k,tag in zip(exp['keyframes'],tags['keyframes']):
        if k['frame_id']!=tag['frame_id']: parser.error('Keyframe order differs')
        point_path=e1/'pointmaps'/k['file']; score_path=e2/tag['result_dir']/'semantic_scores.npz'
        if sha256(point_path)!=k['sha256'] or sha256(score_path)!=tag['semantic_scores_sha256']:
            parser.error('E1a/E2a artifact hash mismatch')
        with np.load(point_path,allow_pickle=False) as ar: data={x:ar[x].copy() for x in ar.files}
        with np.load(score_path,allow_pickle=False) as ar:
            labels=ar['label_id'].astype(np.uint8); label_names=[str(x) for x in ar['labels'].tolist()]
        ordinal=int(k['ordinal']); local_ids=region_archive[f'region_ids_kf_{ordinal:03d}'].astype(np.int32)
        valid=data['valid'].astype(bool)&np.isfinite(data['point_world']).all(-1)
        source=next((x for x in source_manifest['frames'] if int(x['sequence_index'])==int(k['frame_id'])),None)
        if source is None: parser.error(f"source RGB mapping missing frame {k['frame_id']}")
        depth_path=args.depth_root/f"depth{int(k['frame_id']):06d}.png"
        raw,resize_crop=source_depth_grid(depth_path,data['point_world'].shape[:2])
        depth_m=raw.astype(np.float32)/float(cam['scale'])
        gt_cam,intrinsics=backproject(depth_m,cam)
        pose=traj[int(k['frame_id'])]
        gt_world=gt_cam@pose[:3,:3].T+pose[:3,3]
        gtvalid=np.isfinite(depth_m)&(depth_m>1e-6)&np.isfinite(gt_world).all(-1)
        eval_valid=valid & gtvalid
        with np.load(e4/f"refined_kf_{ordinal:03d}_frame_{int(k['frame_id']):08d}.npz",allow_pickle=False) as r:
            b3=r['point_world_refined'].astype(np.float32)
        if b3.shape!=data['point_world'].shape: parser.error('E4a output grid mismatch')
        frames.append({"ordinal":ordinal,"frame_id":int(k['frame_id']),"data":data,"labels":labels,"label_names":label_names,
                       "local_regions":local_ids,"valid":valid,"source_record":source,"depth_path":depth_path,
                       "depth_m":depth_m,"gt_cam":gt_cam,"gt_world":gt_world,"gt_valid":gtvalid,"eval_valid":eval_valid,
                       "resize_crop":resize_crop,"intrinsics":intrinsics,"b3":b3})
        records.append({"ordinal":ordinal,"frame_id":int(k['frame_id']),"rgb_sha256":source['source_sha256'],"depth_sha256":sha256(depth_path),"pointmap_sha256":k['sha256']})

    spacing=float(temporal['global_median_local_spacing_world_units']); radius=float(temporal['association_radius_world_units'])
    # Geometry-only Regions use seed-anchored plane growing, with semantics removed.
    region_config=json.loads((Path(__file__).resolve().parents[1]/'configs/e3a_temporal_region_association.json').read_text())
    geometry_cfg=json.loads((Path(__file__).resolve().parents[1]/'configs/e5a_multikeyframe_gt_evaluation.json').read_text())['geometry_only_regions']
    geom_ids={}
    for f in frames:
        geom_ids[f['ordinal']]=geometry_only_regions(f['data']['point_world'].astype(np.float32),f['valid'],geometry_cfg)
    min_corr=int(region_config['association']['min_mutual_correspondence_pixels'])
    min_overlap=float(region_config['association']['min_bidirectional_correspondence_overlap_fraction'])
    min_region_pixels=int(region_config['association']['min_region_pixels'])
    geom_scores,geom_links=correspondence_links(frames,geom_ids,radius,spacing,min_corr,min_overlap,min_region_pixels)
    semantic_scores={}
    for edge in temporal['candidate_edges']:
        if edge['decision']!='accepted': continue
        p90_link=next((x for x in refined_summary['accepted_link_error_scores']
                       if x['from_keyframe_ordinal']==edge['from']['keyframe_ordinal']
                       and x['from_local_region_id']==edge['from']['local_region_id']
                       and x['to_local_region_id']==edge['to']['local_region_id']),None)
        if p90_link is None: continue
        for key in ((edge['from']['keyframe_ordinal'],edge['from']['local_region_id']),(edge['to']['keyframe_ordinal'],edge['to']['local_region_id'])):
            item=semantic_scores.setdefault(key,{"max_p90_spacing_ratio":0.0,"correspondence_count":0,"links":[]})
            item['max_p90_spacing_ratio']=max(item['max_p90_spacing_ratio'],p90_link['p90_spacing_ratio'])
            item['correspondence_count']+=p90_link['mutual_correspondence_count'];item['links'].append(p90_link)
    # Evaluate B1/B2 with the exact frame-local optimizer and B3 from the persistent merged optimizer.
    methods={"B0_original":[f['data']['point_world'].astype(np.float32) for f in frames],
             "B3_semantic_temporal":[f['b3'] for f in frames]}
    method_details={}
    for name,region_map,scores,semantic in (
        ("B1_geometry_only",geom_ids,geom_scores,False),
        ("B2_semantic_frame_local",{f['ordinal']:f['local_regions'] for f in frames},semantic_scores,True),
    ):
        outputs=[];detail=[]
        for f in frames:
            local_scores={}
            for (ordinal,rid),value in scores.items():
                if ordinal==f['ordinal']:
                    local_scores[(ordinal,rid)]=value
                    value['observation_count']=2 if value.get('links') else 0
            points,mask,rows=refine_frame_local(f,region_map[f['ordinal']],local_scores,spacing,optimizer_config,semantic)
            outputs.append(points);detail.extend(rows)
        methods[name]=outputs
        method_details[name]={"accepted_geometry_links":geom_links if not semantic else None,
                              "candidate_regions":detail,"modified_pixel_count":int(sum(np.count_nonzero(np.linalg.norm(x-f['data']['point_world'],axis=-1)>0) for x,f in zip(outputs,frames)))}

    # One global evaluation Sim(3), estimated only from B0 and reused for B0-B3.
    fit_source=[];fit_target=[]
    for f in frames:
        yy,xx=np.indices(f['eval_valid'].shape);sample=f['eval_valid']&((yy%2)==0)&((xx%2)==0)
        fit_source.append(f['data']['point_world'][sample].astype(np.float64));fit_target.append(f['gt_world'][sample].astype(np.float64))
    scale,rotation,translation=fit_umeyama(np.concatenate(fit_source),np.concatenate(fit_target))
    aligned={name:[apply_sim3(points.astype(np.float64),scale,rotation,translation).astype(np.float32) for points in arrays]
             for name,arrays in methods.items()}
    tau=float(config['outlier_threshold_m']);metrics={};keyframe_metrics={}
    semantic_plane_ids={i for i,n in enumerate(frames[0]['label_names']) if n in {'floor','wall','ceiling'}}
    for name,arrays in aligned.items():
        all_errors=[];all_masks=[];plane_errors=[];plane_masks=[];all_pred=[];all_gt=[]
        per_frame=[];normal_errors=[];boundary_errors=[]
        for f,pred in zip(frames,arrays):
            gt=f['gt_world'];mask=f['eval_valid']
            errors=np.linalg.norm(pred-gt,axis=-1)
            plane=mask&np.isin(f['labels'],list(semantic_plane_ids))
            per_frame.append({"frame_id":f['frame_id'],"all":summarize(errors,mask,tau),"semantic_plane":summarize(errors,plane,tau)})
            all_errors.append(errors[mask]);plane_errors.append(errors[plane]);all_masks.append(mask);plane_masks.append(plane)
            all_pred.append(pred[mask]);all_gt.append(gt[mask])
            pn=normals(pred,mask);gn=normals(gt,mask);nm=mask&np.isfinite(pn).all(-1)&np.isfinite(gn).all(-1)
            dot=np.clip(np.abs(np.sum(pn*gn,axis=-1)),0,1);normal_errors.extend(np.rad2deg(np.arccos(dot[nm])).tolist())
            boundary=np.zeros(mask.shape,dtype=bool)
            boundary[:,1:] |= (f['labels'][:,1:]!=f['labels'][:,:-1])
            boundary[1:,:] |= (f['labels'][1:,:]!=f['labels'][:-1,:])
            pair_err=[]
            # Direct neighboring boundary distances, preserving image adjacency.
            valid_h=mask[:,1:]&mask[:,:-1]&((f['labels'][:,1:]!=f['labels'][:,:-1]))
            valid_v=mask[1:,:]&mask[:-1,:]&((f['labels'][1:,:]!=f['labels'][:-1,:]))
            if valid_h.any():
                dp=np.linalg.norm(pred[:,1:]-pred[:,:-1],axis=-1);dg=np.linalg.norm(gt[:,1:]-gt[:,:-1],axis=-1);pair_err.extend(np.abs(dp[valid_h]-dg[valid_h]).tolist())
            if valid_v.any():
                dp=np.linalg.norm(pred[1:,:]-pred[:-1,:],axis=-1);dg=np.linalg.norm(gt[1:,:]-gt[:-1,:],axis=-1);pair_err.extend(np.abs(dp[valid_v]-dg[valid_v]).tolist())
            boundary_errors.extend(pair_err)
        scene_errors=np.concatenate(all_errors);scene_plane=np.concatenate(plane_errors)
        precision=summarize(scene_errors,np.ones(len(scene_errors),dtype=bool),tau)
        plane_summary=summarize(scene_plane,np.ones(len(scene_plane),dtype=bool),tau)
        metrics[name]={"all_keyframe_point_correspondences":precision,"semantic_plane_pixels":plane_summary,
                       "normal_error_degrees":{"count":len(normal_errors),"mean":float(np.mean(normal_errors)) if normal_errors else None,"median":float(np.median(normal_errors)) if normal_errors else None,"p95":float(np.percentile(normal_errors,95)) if normal_errors else None},
                       "semantic_boundary_gap_error_m":{"count":len(boundary_errors),"mean":float(np.mean(boundary_errors)) if boundary_errors else None,"median":float(np.median(boundary_errors)) if boundary_errors else None},
                       "keyframes":per_frame,"point_coverage_count":int(len(scene_errors))}

    # Scene-level nearest-neighbor surface F-score on a deterministic 2x2 pixel lattice.
    fscore={}
    for name,arrays in aligned.items():
        pred_parts=[];gt_parts=[]
        for f,pred in zip(frames,arrays):
            yy,xx=np.indices(f['eval_valid'].shape);sample=f['eval_valid']&((yy%2)==0)&((xx%2)==0)
            pred_parts.append(pred[sample].astype(np.float64));gt_parts.append(f['gt_world'][sample].astype(np.float64))
        pred_cloud=np.concatenate(pred_parts);gt_cloud=np.concatenate(gt_parts)
        dpg=cKDTree(gt_cloud).query(pred_cloud,k=1,workers=-1)[0]
        dgp=cKDTree(pred_cloud).query(gt_cloud,k=1,workers=-1)[0]
        precision=float(np.mean(dpg<=tau));recall=float(np.mean(dgp<=tau))
        fscore[name]={"precision_at_5cm":precision,"recall_at_5cm":recall,"fscore_at_5cm":2*precision*recall/max(precision+recall,1e-12),"predicted_points":len(pred_cloud),"gt_points":len(gt_cloud)}

    summary={"stage":"E5a_multikeyframe_gt_evaluation","status":"completed","scene":"Replica/room0",
             "keyframe_count":len(frames),"keyframes":records,"source_manifests":{
                 "e1a_sha256":sha256(e1/'pointmaps/export_manifest.json'),"e2a_sha256":sha256(e2/'keyframes_manifest.json'),
                 "e3a_sha256":sha256(e3/'temporal_regions.json'),"e4a_sha256":sha256(e4/'refinement_summary.json')},
             "gt_sources":{"camera_params_sha256":sha256(args.camera_params),"trajectory_sha256":sha256(args.trajectory),
                 "depth_root":str(args.depth_root.resolve()),"depth_scale":float(cam['scale']),
                 "pose_convention":"Replica traj.txt camera-to-world; GT depth backprojections transformed into GT world per frame",
                 "metric":"same-pixel point distance in GT world after one B0-only scene Sim(3); not mesh point-to-surface distance"},
             "common_sim3":{"estimated_from":"B0 only, all Keyframes, deterministic even-row/even-column valid lattice",
                 "scale":scale,"rotation":rotation.tolist(),"translation":translation.tolist(),"reused_for_all_methods":True},
             "outlier_threshold_m":tau,"metrics":metrics,"scene_surface_fscore":fscore,
             "method_details":method_details,"method_note":"B1/B2 share the same bounded frame-local optimizer; B3 uses persistent merged Regions with the same score, plane gates, loss, displacement limit, and boundary freeze. B4 oracle semantic GT masks were not available in the supplied Replica export and are not included.",
             "config":config,"elapsed_seconds":time.perf_counter()-start}
    (args.output/'metrics.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps({"scene":summary['scene'],"keyframe_count":len(frames),"common_sim3_scale":scale,
                      "metrics":{k:v['all_keyframe_point_correspondences']['rmse_m'] for k,v in metrics.items()},
                      "scene_surface_fscore":{k:v['fscore_at_5cm'] for k,v in fscore.items()},"elapsed_seconds":summary['elapsed_seconds']},indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
