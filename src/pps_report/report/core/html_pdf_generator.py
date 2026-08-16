import os
import sys
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from matplotlib import pyplot as plt
import pdfkit
from pps_report.utils.path_helper import resource_path

logger = logging.getLogger(__name__)


class HTMLPDFGenerator:

    TEMPLATE_NAME = 'report_template.html'

    def __init__(self, output_path):
        self.output_path = output_path

    def generate(self, ctx):
        html = self._render_template(ctx)

        wkhtmltopdf_path = self._find_wkhtmltopdf()
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as html_file:
            html_file.write(html)
            html_path = html_file.name

        try:
            options = {
                'enable-local-file-access': None,
                'page-size': 'A4',
                'margin-top': '10mm',
                'margin-bottom': '5mm',
                'margin-left': '10mm',
                'margin-right': '10mm',
                'zoom': '1.0',
                'footer-spacing': '2',
            }
            pdfkit.from_file(html_path, self.output_path, options=options, configuration=config,verbose=True)
        except Exception as exc:
            logger.error("wkhtmltopdf failed: %s", exc)
            raise RuntimeError(f"wkhtmltopdf failed: {exc}") from exc
        finally:
            try:
                os.unlink(html_path)
            except OSError:
                pass

        return self.output_path

    def _render_template(self, ctx):
        env = Environment(
            loader=FileSystemLoader(Path(__file__).resolve().parents[1] / 'templates'),
            autoescape=select_autoescape(['html', 'xml'])
        )
        template = env.get_template(self.TEMPLATE_NAME)

        project = ctx.get('project_info')
        result = ctx.get('calculation_result')
        dist = ctx.get('thickness_distribution')
        visible_layers = ctx.get('visible_layers', [])
        target_min = ctx.get('target_min')
        target_max = ctx.get('target_max')
        screenshot_path = ctx.get('screenshot_path')

        chart_path = self._create_distribution_chart(dist, target_min, target_max) if dist is not None else None

        visible_layers_name = ", ".join(layer.name for layer in visible_layers)
        logger.debug("Visible layers for report: %s", visible_layers_name)

        return template.render(
            title='SHOTCRETE THICKNESS REPORT',
            logo_path=self._escape_path(resource_path("report/assets/images/logo.png")),
            project_rows=self._project_rows(project, result, target_min, target_max, ctx),
            result_main_rows=self._result_main_rows(result),
            result_stats_rows=self._result_stats_rows(result),
            distribution_rows=self._distribution_rows(dist, target_min, target_max),
            chart_path=chart_path and self._escape_path(chart_path),
            segment_notes=self._segment_notes(visible_layers),
            screenshot_path=self._escape_path(screenshot_path) if screenshot_path else None,
            layer_name=visible_layers_name,
            current_date=datetime.now().strftime("%d-%b-%Y")
        )

    def _project_rows(self, project, result, target_min, target_max, ctx):
        if project is None:
            return []

        # Left column labels and values
        left_labels = ['Site', 'Job Name', 'Date', 'Time', 'Source File']
        left_values = [
            project.project_name,
            project.job_number,
            project.formatted_date,
            project.formatted_time,
            project.original_filename
        ]

        # Right column labels and values
        right_labels = ['Shotcrete Applied', 'Average Thickness', 'Shotcrete Volume', 'Area Completed/Total']
        right_values = []
        
        if result is not None:
            if target_min is not None and target_max is not None:
                right_values.append(self._format_shotcrete_applied(target_min, target_max))
            else:
                right_values.append('N/A')
            right_values.append(f'{result.mean_thickness_mm:.0f} mm')
            right_values.append(f'{result.volume_m3:.1f} m³')
            
            completed_area = result.area_reached_target_m2
            total_area = result.surface_area_m2
            if total_area is not None:
                area_value = f'{completed_area:.1f} / {total_area:.1f} m² ({(completed_area/total_area*100):.0f}%)'
            else:
                area_value = f'{completed_area:.1f} m²'
            right_values.append(area_value)
        else:
            right_values.extend(['N/A', 'N/A', 'N/A'])
        


        # Combine into rows of 4 columns: label1, value1, label2, value2
        rows = []
        max_len = max(len(left_labels), len(right_labels))
        
        for i in range(max_len):
            label1 = left_labels[i] if i < len(left_labels) else ''
            value1 = left_values[i] if i < len(left_values) else ''
            label2 = right_labels[i] if i < len(right_labels) else ''
            value2 = right_values[i] if i < len(right_values) else ''
            rows.append((label1, value1, label2, value2))

        return rows

    def _result_main_rows(self, result):
        if result is None:
            return []

        return [
            {'label': 'Surface Area', 'value': f'{result.surface_area_m2:.4f} m²'},
            {'label': 'Volume', 'value': f'{result.volume_m3:.6f} m³'},
        ]

    def _result_stats_rows(self, result):
        if result is None:
            return []

        return [
            {'label': 'Mean Thickness', 'value': f'{result.mean_thickness_mm:.2f} mm'},
            {'label': 'Min Thickness', 'value': f'{result.min_thickness_mm:.2f} mm'},
            {'label': 'Max Thickness', 'value': f'{result.max_thickness_mm:.2f} mm'},
            {'label': 'Std Deviation', 'value': f'{result.std_thickness_mm:.2f} mm'},
            {'label': 'Total Points', 'value': f'{result.num_points:,}'},
        ]

    def _distribution_rows(self, dist, target_min, target_max):
        if dist is None:
            return []

        return [
            {'label': 'Below Target', 'value': f'{dist.below_target:,}'},
            {'label': 'Within Target', 'value': f'{dist.within_target:,}'},
            {'label': 'Above Target', 'value': f'{dist.above_target:,}'},
            {'label': 'Target Range', 'value': f'{target_min} - {target_max} mm'},
        ]

    def _format_shotcrete_applied(self, target_min, target_max):
        if target_min is None or target_max is None:
            return 'N/A'

        if target_min == target_max:
            return f'{target_min:.0f} (mm) ±0 mm'

        midpoint = (target_min + target_max) / 2
        tolerance = abs(target_max - target_min) / 2
        return f'{midpoint:.0f} (mm) ±{tolerance:.0f} mm'

    def _segment_notes(self, visible_layers):
        notes = []
        for layer in visible_layers:
            annotations = getattr(layer, 'annotations', [])
            if not annotations:
                continue

            notes.append({
                'layer_name': layer.name,
                'text': '\n\n'.join(ann['text'] for ann in annotations),
            })
        return notes

    def _create_distribution_chart(self, dist, tmin, tmax):
        if dist is None:
            return None

        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.margins(y=0.2)
        labels = [f'< {int(tmin)}', f'{int(tmin)}-{int(tmax)}', f'> {int(tmax)}']
        values = [dist.below_target, dist.within_target, dist.above_target]
        colors = ["#ff6060", "#64ffa0", "#315aff"]

        total = sum(values) if sum(values) > 0 else 1
        bars = ax.bar(labels, values, color=colors)

        for bar in bars:
            height = bar.get_height()
            percent = (height / total) * 100
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height,
                f'{int(height):,}\n({percent:.0f}%)',
                ha='center',
                va='bottom',
                fontsize=12,
            )

        ax.set_title('Thickness Distribution', fontsize=16, fontweight='bold')
        ax.set_xlabel('Thickness Range (mm)')
        ax.set_ylabel('Number of Points')
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        plt.tight_layout()

        tmp_dir = tempfile.gettempdir()
        chart_path = os.path.join(tmp_dir, 'pps_report_distribution.png')
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        logger.debug("Saved distribution chart to: %s", chart_path)
        return chart_path

    def _escape_path(self, path):
        if path is None:
            return ''
        
        path = Path(path).resolve().as_uri()
        return path

    def _find_wkhtmltopdf(self):
        from shutil import which

        # Thử PATH hệ thống trước
        wkhtmltopdf = which('wkhtmltopdf')
        if wkhtmltopdf:
            return wkhtmltopdf

        # Xác định tất cả base có thể
        bases = set()

        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            bases.add(exe_dir)
            bases.add(os.path.join(exe_dir, '_internal'))
        
        # Luôn thêm các base từ __file__
        try:
            file_dir = os.path.dirname(os.path.abspath(__file__))
            bases.add(file_dir)
            bases.add(os.path.dirname(file_dir))         # lên 1 cấp
            bases.add(os.path.dirname(os.path.dirname(file_dir)))  # lên 2 cấp
        except Exception:
            pass

        # Thêm thư mục hiện tại
        bases.add(os.getcwd())

        rel = os.path.join('report', 'packages', 'wkhtmltox', 'bin', 'wkhtmltopdf.exe')

        for base in bases:
            candidate = os.path.join(base, rel)
            logger.debug("checking: %s", candidate)
            if os.path.exists(candidate):
                logger.debug("found: %s", candidate)
                return candidate

        logger.error(
            "wkhtmltopdf not found. sys.executable=%s cwd=%s frozen=%s",
            sys.executable, os.getcwd(), getattr(sys, 'frozen', False),
        )

        raise RuntimeError(
            'wkhtmltopdf executable not found.\n'
            f'Searched bases: {bases}\n'
            f'Relative path: {rel}'
        )
