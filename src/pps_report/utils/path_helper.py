import sys
import os

def resource_path(rel):
    """Trả về absolute path đúng khi chạy từ source hoặc exe."""
    if getattr(sys, 'frozen', False):
        # PyInstaller onedir — thử cả 2 vị trí
        base_exe = os.path.dirname(sys.executable)
        base_internal = os.path.join(base_exe, '_internal')
        
        # Ưu tiên _internal trước
        candidate = os.path.join(base_internal, rel)
        if os.path.exists(candidate):
            return candidate
        return os.path.join(base_exe, rel)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        # utils/ nằm trong project root, lên 1 cấp
        root = os.path.dirname(base)
        return os.path.join(root, rel)