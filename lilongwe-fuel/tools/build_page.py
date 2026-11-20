"""Inline Leaflet's CSS into the page: site/index.src.html -> site/index.html"""
import pathlib
R = pathlib.Path(__file__).resolve().parent.parent
src = (R / "site/index.src.html").read_text()
css = (R / "tools/leaflet-1.9.4.min.css").read_text()
(R / "site/index.html").write_text(src.replace("/*LEAFLET_CSS*/", css))
print("ok site/index.html")
