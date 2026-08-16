# Tunnel Concrete Thickness Analyzer

Phần mềm phân tích độ dày bê tông phun đường hầm từ dữ liệu Point Cloud (.ply)

## Tính năng

- **Tải và hiển thị 3D**: Mở file PLY với các trường scalar tùy chỉnh (distances)
- **Visualization tương tác**: Xoay, zoom, pan với bảng màu tùy chỉnh
- **Công cụ chọn vùng (Segment)**: Chọn vùng bằng cách kéo chuột hoặc theo khoảng độ dày
- **Tính toán tự động**:
  - Diện tích bề mặt (m²)
  - Thể tích bê tông (m³, lít)
  - Độ dày trung bình, min, max, độ lệch chuẩn
  - Phân bố độ dày theo tiêu chuẩn
- **Xuất báo cáo PDF**: Báo cáo đầy đủ với thông tin dự án và biểu đồ histogram

## Cài đặt

### Yêu cầu hệ thống
- Python 3.9 trở lên
- Windows / macOS / Linux

### Cài đặt thư viện

```bash
cd PPS_Report_PC
pip install -e .[dev]
```

(hoặc `pip install -r requirements.txt` để cài dependency mà không cài package ở chế độ editable)

## Sử dụng

### Chạy ứng dụng

```bash
python main.py
```

### Quy trình làm việc

1. **Mở file PLY**: File > Mở file PLY... hoặc Ctrl+O
2. **Chọn trường độ dày**: Chọn trường scalar chứa dữ liệu độ dày (distances)
3. **Cài đặt ngưỡng**: Nhập độ dày tối thiểu và tối đa mong muốn
4. **Chọn vùng (tùy chọn)**: 
   - Bật "Chế độ chọn" và kéo chuột để chọn vùng
   - Hoặc chọn theo khoảng độ dày
5. **Tính toán**: Nhấn nút "Tính toán"
6. **Xuất báo cáo**: Nhấn "Xuất báo cáo PDF"

### Định dạng tên file

Phần mềm tự động phân tích thông tin từ tên file PLY theo format:

```
projectname#jobnumber#hhmmss#name.ply
```

Ví dụ: `TunnelA#JOB001#143025#Section1.ply`

- `projectname`: Tên dự án (TunnelA)
- `jobnumber`: Mã công việc (JOB001)  
- `hhmmss`: Thời gian scan (14:30:25)
- `name`: Tên segment (Section1)

### Phím tắt

| Phím | Chức năng |
|------|-----------|
| Ctrl+O | Mở file |
| Ctrl+E | Xuất PDF |
| Ctrl+Q | Thoát |
| R | Reset view |
| T | Top view |
| F | Front view |
| S | Side view |

## Cấu trúc project

```
PPS_Report_PC/
├── main.py                 # Thin entry-point shim (build.spec target)
├── pyproject.toml          # Package + dependency config (canonical)
├── requirements.txt        # Kept in sync with pyproject.toml for `pip install -r`
├── build.spec              # PyInstaller build config
├── src/pps_report/
│   ├── __main__.py         # Real entry point: QApplication setup, theme, launch
│   ├── core/                # Core logic — PLY I/O, calculator, segmentation, layers
│   ├── gui/                  # PySide6 GUI — main window, 3D viewer, annotations, theme
│   ├── report/                # PDF report generation (Jinja2 HTML + wkhtmltopdf)
│   └── utils/                 # Path helpers, misc utilities
├── tests/                   # pytest suite
└── scripts/                 # Standalone utility scripts (not part of the package)
```

## Lưu ý

- File PLY cần có trường scalar chứa độ dày (mặc định: "distances")
- Đơn vị độ dày trong file PLY phải là mm
- Đơn vị tọa độ (x, y, z) trong file PLY phải là mét

## License

Ứng dụng dùng các thư viện mã nguồn mở an toàn cho phát hành closed-source:
PySide6 (LGPL-3, dual-license), VTK (BSD), pyvista/pyvistaqt (MIT), open3d (MIT),
numpy/scipy (BSD), matplotlib (PSF), jinja2 (BSD), Pillow (HPND), pdfkit (MIT).
PLY được đọc qua `open3d.t.io` (MIT) — không dùng `plyfile` (GPL-3.0) để tránh
copyleft khi phát hành bản đóng gói.

PDF được xuất qua `pdfkit` + `wkhtmltopdf` (binary LGPL-2, gọi qua subprocess
nên không ảnh hưởng license code Python). Bản build cài sẵn `wkhtmltopdf.exe`
trong gói cài đặt — người dùng cuối không cần tự cài thêm gì.

## Build

```bash
pip install pyinstaller
```

Trước khi build lần đầu (hoặc trên máy dev mới), tải sẵn `wkhtmltopdf.exe`
(không commit vào git vì file lớn — `packages/` nằm trong `.gitignore`) và đặt vào
`src/pps_report/report/packages/wkhtmltox/bin/wkhtmltopdf.exe`:

```bash
curl -L -o wkhtmltox.7z https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.mxe-cross-win64.7z
7z x wkhtmltox.7z -oextracted
# copy extracted/wkhtmltox/bin/wkhtmltopdf.exe -> src/pps_report/report/packages/wkhtmltox/bin/
```

Sau đó build:

```bash
Remove-Item -Recurse -Force build, dist
pyinstaller build.spec
```

`build.spec` sẽ tự đóng gói `wkhtmltopdf.exe` cùng ứng dụng (nằm trong
`src/pps_report/report/`, được bundle vào `dist/.../report/packages/...`).