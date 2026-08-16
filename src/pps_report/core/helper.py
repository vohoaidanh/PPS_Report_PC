from pps_report.utils.utils import timeit
@timeit
def surface_area(
    pcd,
    radii=(0.1, 0.15),
    estimate_normals=True
) -> float:
    """
    Tính diện tích bề mặt point cloud bằng Ball Pivoting Algorithm (BPA)

    Parameters
    ----------
    pcd : open3d.geometry.PointCloud
        Point cloud đầu vào
    radii : tuple
        Danh sách bán kính ball (nên tăng dần)
    estimate_normals : bool
        Có tự estimate normals hay không

    Returns
    -------
    area : float
        Diện tích bề mặt (đơn vị theo cloud)
    """
    import open3d as o3d
    import copy

    pcd = copy.deepcopy(pcd)

    if isinstance(pcd, o3d.t.geometry.PointCloud):
        pcd = pcd.to_legacy()
    

    pcd = pcd.voxel_down_sample(voxel_size=min(radii) / 2)

    cl, ind = pcd.remove_radius_outlier(nb_points=8, radius=2*min(radii))
    pcd = pcd.select_by_index(ind)

    if len(pcd.points) == 0:
        return 0.0

    if estimate_normals:
        if not pcd.has_normals():
            pcd.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(
                    radius=max(radii) * 2,
                    max_nn=30
                )
            )
        if pcd.has_normals():
            try:
                pcd.orient_normals_consistent_tangent_plane(50)
            except Exception:
                pass

    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
        pcd,
        o3d.utility.DoubleVector(radii)
    )

    # Tính diện tích
    area = mesh.get_surface_area()
    return area