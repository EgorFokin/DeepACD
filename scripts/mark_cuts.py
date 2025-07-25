import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..","lib", "build"))
import open3d as o3d
import numpy as np
import matplotlib.pyplot as plt
import trimesh
import torch
from utils.ACDgen import ACDgen
from model.model import ACDModel
import lib_neural_acd
import argparse
from utils.misc import load_config, get_point_cloud

def normalize_points(pcd):
    points = np.asarray(pcd.points)
    centroid = np.mean(points, axis=0)
    points -= centroid
    max_distance = np.max(np.linalg.norm(points, axis=1))
    points /= max_distance
    pcd.points = o3d.utility.Vector3dVector(points)

def load_model(checkpoint):
    model = ACDModel().cuda()
    state_dict = torch.load(checkpoint, weights_only=True)["state_dict"]
    model.load_state_dict(state_dict)
    model.eval()
    return model.cuda()

def show_pcd(points, distances):
    colormap = plt.get_cmap("jet")
    colors = colormap(distances)[:, :3]  # Get RGB colors from the colormap
    point_cloud = trimesh.points.PointCloud(points, colors=colors)
    point_cloud.show()

def get_curvature(mesh, points, radius):
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)

    # for _ in range(5):
    #     vertices,triangles =  trimesh.remesh.subdivide(vertices, triangles)

    tmesh = trimesh.Trimesh(vertices=vertices, faces=triangles)

    # tmesh.show()
    curvature = trimesh.curvature.discrete_gaussian_curvature_measure(tmesh, points, radius)

    curvature[curvature >= -0.1] = 0
    curvature[curvature < -0.1] = 1
    return curvature


def mark_cuts(points, checkpoint, config, no_threshold=False):

    if isinstance(points, np.ndarray):
        points = torch.tensor(points, dtype=torch.float32)
    
    if isinstance(points, list):
        points = torch.stack([torch.tensor(p, dtype=torch.float32) for p in points], dim=0)

    batched = True
    points = points.cuda()

    if points.ndim == 2:
        points = points.unsqueeze(0)
        batched = False

    model = load_model(checkpoint)

    with torch.no_grad():

        distances = []

        for start in range(0, points.shape[0], config.model.batch_size):
            end = min(start + config.model.batch_size, points.shape[0])
            batch_points = points[start:end]
    
            pred = model(batch_points, apply_sigmoid=False)

            distances.append(pred)
        distances = torch.cat(distances, dim=0)

        if not batched:
            distances = distances.squeeze(0)

        distances = distances.cpu().numpy()

    if no_threshold:
        return distances

    distances[distances < config.general.cut_point_threshold] = 0
    distances[distances >= config.general.cut_point_threshold] = 1

    return distances

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mark cuts in point cloud using ACD model.")
    parser.add_argument("--checkpoint", type=str, default="model/checkpoint.ckpt", help="Path to the model checkpoint.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility.")
    parser.add_argument("--gt", action="store_true", help="Use ground truth points instead of model predictions.")
    parser.add_argument("--config", type=str, default="config/config.yaml", help="Path to the configuration file.")
    parser.add_argument("--no-threshold", action="store_true", help="Do not apply thresholding to cut points.")
    parser.add_argument("--use-curvature", action="store_true", help="Use curvature instead of model predictions.")
    
    args = parser.parse_args()
    
    config = load_config(args.config)

    it = ACDgen(output_meshes=True).__iter__()
    if args.seed is not None:
        lib_neural_acd.set_seed(args.seed)
    points, distances_t, structure = next(it)    

    pcd = get_point_cloud(structure)
    points = np.asarray(pcd.points)

    if args.gt:
        distances = distances_t
    elif args.use_curvature:
        distances = get_curvature(structure, points, radius=0.02)
    else:
        distances = mark_cuts(points, args.checkpoint, config, args.no_threshold )

   

    show_pcd(points, distances)


