import vtk
from typing import Optional, List, Dict
import time
from PySide6.QtCore import QTimer
# ============================================================ VTK polygon picker
class VTKPolygonPicker:
    """
    CloudCompare-style polygon selection drawn in VTK's 2D coordinate space.

    Controls
    --------
    Left click        – add vertex
    Double-click      – close & apply (≥ 3 pts)
    Right click       – close & apply (≥ 3 pts) / cancel
    Enter             – close & apply (≥ 3 pts)
    Backspace         – remove last vertex
    ESC               – cancel
    """

    def __init__(self, plotter, on_closed, on_cancelled, overlay_renderer=None):
        self._plotter      = plotter
        self._ren_win      = plotter.ren_win
        self._on_closed    = on_closed
        self._on_cancelled = on_cancelled

        self._pts: List     = []
        self._active        = False
        self._obs_tags      = []
        self._t_last_click  = 0.0

        self._iren = self._ren_win.GetInteractor()

        if overlay_renderer is not None:
            self._ren2d = overlay_renderer
        else:
            self._ren2d = vtk.vtkRenderer()
            self._ren2d.SetLayer(1)
            self._ren2d.InteractiveOff()
            self._ren_win.SetNumberOfLayers(2)
            self._ren_win.AddRenderer(self._ren2d)

        self._a_edges = None
        self._a_verts = None
        self._a_prev  = None
        self._a_text  = None

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self):
        self._pts           = []
        self._active        = True
        self._t_last_click  = 0.0
        self._clear_actors()

        self._iren.SetInteractorStyle(vtk.vtkInteractorStyleUser())

        self._obs_tags = [
            self._iren.AddObserver('LeftButtonPressEvent',  self._on_left),
            self._iren.AddObserver('RightButtonPressEvent', self._on_right),
            self._iren.AddObserver('MouseMoveEvent',        self._on_move),
            self._iren.AddObserver('KeyPressEvent',         self._on_key),
        ]
        self._redraw()
        self._ren_win.Render()

    def stop(self):
        self._active = False
        for tag in self._obs_tags:
            try: self._iren.RemoveObserver(tag)
            except: pass
        self._obs_tags = []
        self._clear_actors()
        QTimer.singleShot(0, self._restore_camera)

    def _restore_camera(self):
        try:
            self._plotter.enable_rubber_band_style()
        except Exception:
            try:
                self._iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
            except Exception:
                pass
        try:
            self._ren_win.Render()
        except Exception:
            pass

    def _on_left(self, obj, event):
        if not self._active:
            return
        x, y = self._iren.GetEventPosition()
        now  = time.time()

        is_dbl = (
            self._pts
            and now - self._t_last_click < 0.35
            and abs(x - self._pts[-1][0]) < 8
            and abs(y - self._pts[-1][1]) < 8
        )
        self._t_last_click = now

        if is_dbl:
            if len(self._pts) >= 3:
                pts = list(self._pts)
                self.stop()
                self._on_closed(pts)
            return

        self._pts.append((x, y))
        self._redraw()
        self._ren_win.Render()

    def _on_right(self, obj, event):
        if not self._active:
            return
        if len(self._pts) >= 3:
            pts = list(self._pts)
            self.stop()
            self._on_closed(pts)
        else:
            self.stop()
            self._on_cancelled()

    def _on_move(self, obj, event):
        if not self._active or not self._pts:
            return
        x, y = self._iren.GetEventPosition()
        self._draw_preview(x, y)
        self._ren_win.Render()

    def _on_key(self, obj, event):
        if not self._active:
            return
        key = self._iren.GetKeySym()
        if key == 'Escape':
            self.stop()
            self._on_cancelled()
        elif key in ('Return', 'KP_Enter') and len(self._pts) >= 3:
            pts = list(self._pts)
            self.stop()
            self._on_closed(pts)
        elif key == 'BackSpace' and self._pts:
            self._pts.pop()
            self._redraw()
            self._ren_win.Render()

    @staticmethod
    def _vtkpts(coords):
        p = vtk.vtkPoints()
        for x, y in coords:
            p.InsertNextPoint(float(x), float(y), 0.0)
        return p

    @staticmethod
    def _actor2d(poly, rgb, lw=None, ps=None, alpha=1.0):
        m = vtk.vtkPolyDataMapper2D()
        m.SetInputData(poly)
        a = vtk.vtkActor2D()
        a.SetMapper(m)
        pr = a.GetProperty()
        pr.SetColor(*rgb)
        pr.SetOpacity(alpha)
        if lw is not None: pr.SetLineWidth(lw)
        if ps is not None: pr.SetPointSize(ps)
        return a

    def _redraw(self):
        for a in (self._a_edges, self._a_verts, self._a_text):
            if a: self._ren2d.RemoveActor(a)
        self._a_edges = self._a_verts = self._a_text = None

        n = len(self._pts)

        if n >= 2:
            pts_v = self._vtkpts(self._pts)
            lines = vtk.vtkCellArray()
            for i in range(n - 1):
                ln = vtk.vtkLine()
                ln.GetPointIds().SetId(0, i)
                ln.GetPointIds().SetId(1, i + 1)
                lines.InsertNextCell(ln)
            poly = vtk.vtkPolyData()
            poly.SetPoints(pts_v); poly.SetLines(lines)
            self._a_edges = self._actor2d(poly, (1.0, 0.55, 0.05), lw=2.5)
            self._ren2d.AddActor(self._a_edges)

        if n >= 1:
            pts_v = self._vtkpts(self._pts)
            verts = vtk.vtkCellArray()
            for i in range(n):
                verts.InsertNextCell(1); verts.InsertCellPoint(i)
            poly = vtk.vtkPolyData()
            poly.SetPoints(pts_v); poly.SetVerts(verts)
            self._a_verts = self._actor2d(poly, (1.0, 0.25, 0.0), ps=9)
            self._ren2d.AddActor(self._a_verts)

        try:
            _, h = self._ren_win.GetSize()
        except Exception:
            h = 600
        msg = (
            f"Left-click: add point [{n}]  |  ESC: cancel"
            if n < 3 else
            f"Right-click/Enter: apply [{n} pts]  |  Backspace: undo  |  ESC: cancel"
        )
        txt = vtk.vtkTextActor()
        txt.SetInput(msg)
        txt.SetPosition(10, max(h - 32, 4))
        p = txt.GetTextProperty()
        p.SetFontSize(13); p.SetColor(1.0, 1.0, 0.3)
        p.SetBold(True);   p.SetShadow(True)
        self._a_text = txt
        self._ren2d.AddActor(self._a_text)

    def _draw_preview(self, mx, my):
        if self._a_prev:
            self._ren2d.RemoveActor(self._a_prev)
            self._a_prev = None
        if not self._pts:
            return

        coords = [self._pts[-1], (mx, my)]
        if len(self._pts) >= 2:
            coords.append(self._pts[0])

        pts_v = self._vtkpts(coords)
        lines = vtk.vtkCellArray()
        l1 = vtk.vtkLine()
        l1.GetPointIds().SetId(0, 0); l1.GetPointIds().SetId(1, 1)
        lines.InsertNextCell(l1)
        if len(self._pts) >= 2:
            l2 = vtk.vtkLine()
            l2.GetPointIds().SetId(0, 1); l2.GetPointIds().SetId(1, 2)
            lines.InsertNextCell(l2)
        poly = vtk.vtkPolyData()
        poly.SetPoints(pts_v); poly.SetLines(lines)
        self._a_prev = self._actor2d(poly, (1.0, 0.85, 0.2), lw=1.5, alpha=0.60)
        self._ren2d.AddActor(self._a_prev)

    def _clear_actors(self):
        for a in (self._a_edges, self._a_verts, self._a_prev, self._a_text):
            if a:
                try: self._ren2d.RemoveActor(a)
                except: pass
        self._a_edges = self._a_verts = self._a_prev = self._a_text = None
        try:
            self._ren_win.Render()
        except Exception:
            pass
