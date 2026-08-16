# Claude Refactor Prompt

## Mục tiêu
Giúp cải tạo lại toàn bộ project Python `PPS_Report_PC` để đạt các tiêu chí:
- Tổ chức rõ ràng theo kiến trúc module/package
- Tách biệt `core` logic, `GUI`, `report`, `utils`
- Loại bỏ các phụ thuộc chéo và cấu trúc import không chuẩn
- Dễ dàng mở rộng, bảo trì và kiểm thử
- Giữ nguyên chức năng hiện tại: đọc PLY, phân tích độ dày bê tông, hiển thị 3D, chọn vùng, tính toán, xuất báo cáo PDF

## Tình trạng hiện tại
Project hiện có cấu trúc như sau:
- `main.py`: entrypoint, check dependency, khởi tạo Qt app
- `core/`: xử lý PLY, parsing filename, calculator, segmentation, layer manager
- `gui/`: giao diện Qt, viewer 3D, annotation, help
- `report/`: báo cáo PDF, templates, styles
- `utils/`: helper chung
- `build.spec`, `requirements.txt`, `README.md`

Một số vấn đề nhận thấy:
- `main.py` dùng `sys.path.insert` để tìm module
- `gui/main_window.py` rất lớn, đang chứa quá nhiều logic giao diện và logic xử lý
- `core/calculator.py` chứa nhiều code comment, không tách rõ phần input validation, business logic, surface area estimation
- Repo chưa có cấu trúc package chuẩn như `src/` hoặc `package/`
- Không có test module rõ ràng
- Folder `dist/` / `build/` là artifact build, nên ignore khi version control

## Yêu cầu cải tạo
1. Thiết kế lại cấu trúc project theo chuẩn Python package:
   - `src/` hoặc `package/` chứa mã nguồn chính
   - `tests/` chứa unit test
   - `README.md`, `requirements.txt`, `.gitignore`
2. Tách module theo trách nhiệm:
   - `core/`: data model, I/O PLY, parsing, tính toán, segmentation, layer manager, service logic
   - `gui/`: chỉ giao diện Qt và interaction, không chứa business logic
   - `report/`: chứa generator report PDF/HTML và template/style
   - `utils/`: helper chung, path helper, time/validation
3. Refactor code:
   - Dùng `dataclass` cho model data như `PointCloudData`, `CalculationResult`, `ThicknessDistribution`, `ProjectInfo`, `Segment`
   - Tách logic đọc PLY (`load_ply`, `get_ply_fields`, `filter_by_distance`) vào module rõ ràng
   - Tách logic phân tích/thống kê sang module riêng
   - Tách giao diện thành các widget nhỏ nếu cần, hoặc chí ít chia `main_window.py` thành các phần quản lý panel và signal handler
4. Xử lý import chuẩn:
   - Loại bỏ `sys.path.append`/`sys.path.insert`
   - Dùng import package nội bộ đúng cách
   - Đảm bảo `main.py` khởi tạo ứng dụng từ package cleanly
5. Đề xuất/triển khai file cấu hình gói:
   - `pyproject.toml` hoặc `setup.cfg`
   - `requirements.txt` hợp lý
6. Thêm đề xuất kiểm thử:
   - Đảm bảo có ít nhất test cho `core/ply_loader.py`, `core/parser.py`, `core/calculator.py`, `core/segmentation.py`
   - Nếu có thể, cung cấp bộ test cơ bản cho chức năng đọc file PLY và tính toán
7. Cải thiện chất lượng code:
   - Dùng `logging` thay vì `print`
   - Dọn comment cũ, loại bỏ code chết
   - Thêm docstring rõ ràng cho hàm và class
   - Làm sạch `report/` package và đặt đúng vị trí

## Giới hạn / chú ý
- Không cần rewrite GUI từ đầu thành framework khác, chỉ cần tái cấu trúc Python/Qt hiện có
- Giữ các thư viện chính: `PyQt5`, `pyvista`, `pyvistaqt`, `numpy`, `plyfile`, `reportlab`, `matplotlib`, `scipy`
- Không cần xử lý file build artifact trong `dist/` hiện tại, nhưng nên đưa `dist/` và `build/` vào `.gitignore`
- Không cần sửa file trong thư mục build/dist của bộ cài đặt đã đóng gói

## Output mong muốn
Claude hãy trả về:
- Đề xuất cấu trúc thư mục chi tiết mới
- Các file chính cần refactor hoặc tạo mới
- Danh sách task refactor cụ thể
- Nếu có thể, một phiên bản sơ bộ `pyproject.toml` và `setup.cfg` mẫu
- Một kế hoạch thực hiện từng bước

## Thông tin phụ
Các module trọng tâm hiện tại:
- `core/ply_loader.py`
- `core/calculator.py`
- `core/segmentation.py`
- `core/filename_parser.py`
- `core/layer_manager.py`
- `gui/main_window.py`
- `gui/viewer_3d.py`
- `report/core/pdf_generator.py`
- `report/templates/shotcrete_template.py`
- `report/styles/style_factory.py`

Project là ứng dụng desktop Windows/macOS/Linux, mục tiêu là phân tích độ dày bê tông phun từ PLY point cloud và xuất báo cáo PDF.
