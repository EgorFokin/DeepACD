from decompose import decompose
import datetime
import os
import open3d as o3d
import numpy as np

if __name__ == "__main__":
    VHACD = "data\\v_hacd"
    DEPTH = 5
    RANDOM_ROTATION = False
    start_time = datetime.datetime.now()
    num_parts = 0
    concavity = 0
    i = 0
    for files in os.listdir(VHACD):
        if files.endswith(".off"):
            mesh = o3d.io.read_triangle_mesh(os.path.join(VHACD, files))
            if RANDOM_ROTATION:
                rotation = mesh.get_rotation_matrix_from_xyz(np.random.rand(3) * 2 * np.pi)
                mesh.rotate(rotation, center=(0, 0, 0))
            parts, hulls, avg_concavity = decompose(mesh, DEPTH)
            num_parts += len(parts)
            concavity += avg_concavity
            print("processed: ", i+1)
            i+=1

    print("runtime: ", datetime.datetime.now() - start_time)
    print("average concavity: ", concavity/i)
    print("average number of parts: ", num_parts/i)
