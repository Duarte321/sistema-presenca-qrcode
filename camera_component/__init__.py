import streamlit.components.v1 as components
import os

_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "frontend")

camera_qr = components.declare_component(
    "camera_qr",
    path=_COMPONENT_DIR,
)
