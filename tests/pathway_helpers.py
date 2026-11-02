from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow


def open_window(qapp, root, tmp_path, size=(1400, 900)):
    window = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    window.show()
    for _ in range(3):
        window.resize(*size)
        qapp.processEvents()
    window.view.render()
    return window


def projected_height(view, bounds) -> float:
    renderer = view.renderer
    ys = []
    for x in bounds[0:2]:
        for y in bounds[2:4]:
            for z in bounds[4:6]:
                renderer.SetWorldPoint(x, y, z, 1.0)
                renderer.WorldToDisplay()
                ys.append(renderer.GetDisplayPoint()[1])
    return (max(ys) - min(ys)) / view.devicePixelRatioF()
