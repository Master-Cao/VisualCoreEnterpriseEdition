import os
import json


def world_to_robot_using_calib(world_xyz, project_root: str):
    try:
        if world_xyz is None:
            return None
        xw, yw, zw = float(world_xyz[0]), float(world_xyz[1]), float(world_xyz[2])
        calib_path = os.path.join(project_root, "configs", "transformation_matrix.json")
        if not os.path.exists(calib_path):
            return None
        with open(calib_path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        mx = data.get("matrix_xy")
        zm = data.get("z_mapping")
        if isinstance(mx, list) and len(mx) == 2 and all(isinstance(r, list) and len(r) == 3 for r in mx) and isinstance(zm, dict):
            a11, a12, a13 = float(mx[0][0]), float(mx[0][1]), float(mx[0][2])
            a21, a22, a23 = float(mx[1][0]), float(mx[1][1]), float(mx[1][2])
            xr = a11 * xw + a12 * yw + a13
            yr = a21 * xw + a22 * yw + a23
            alpha = float(zm.get("alpha", 1.0)) if zm else 1.0
            beta = float(zm.get("beta", 0.0)) if zm else 0.0
            zr = alpha * zw + beta
            if zr < -85.0:
                zr = -85.0
            return [xr, yr, zr]
        M = data.get("matrix")
        if isinstance(M, list) and len(M) == 4 and all(isinstance(r, list) and len(r) == 4 for r in M):
            m = M
            xr = m[0][0]*xw + m[0][1]*yw + m[0][2]*zw + m[0][3]
            yr = m[1][0]*xw + m[1][1]*yw + m[1][2]*zw + m[1][3]
            zr = m[2][0]*xw + m[2][1]*yw + m[2][2]*zw + m[2][3]
            w = m[3][0]*xw + m[3][1]*yw + m[3][2]*zw + m[3][3]
            if w != 0:
                xr, yr, zr = xr / w, yr / w, zr / w
            if zr < -85.0:
                zr = -85.0
            return [xr, yr, zr]
        return None
    except Exception:
        return None

