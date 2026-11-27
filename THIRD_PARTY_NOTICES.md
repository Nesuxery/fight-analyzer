# Third-party components

Fight Analyzer is licensed under the GNU Affero General Public License v3.0 (see
[LICENSE](LICENSE)), because it builds on Ultralytics YOLO, which is AGPL-3.0.

No model weights, videos or fonts are stored in this repository. Models are
downloaded by the setup script from their official sources and checked against
pinned SHA-256 digests; Python and npm packages come from their registries at the
exact versions in `backend/requirements/` and `frontend/package-lock.json`.

| Component | Used for | License |
| --- | --- | --- |
| [Ultralytics](https://github.com/ultralytics/ultralytics) and YOLO26 pose weights | pose estimation, short-term tracking | AGPL-3.0 |
| [PaddleOCR](https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx) `en_PP-OCRv5_mobile_rec` | reading the scorebug clock | Apache-2.0 |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | running the OCR model (CPU) | MIT |
| [PyTorch](https://pytorch.org) | running the pose model | BSD-3-Clause |
| [OpenCV](https://opencv.org) | video decoding, optical flow, image processing | Apache-2.0 |
| [FFmpeg](https://ffmpeg.org) via imageio-ffmpeg | analysis copy and MP4 export | LGPL/GPL (depending on the build) |
| [FastAPI](https://fastapi.tiangolo.com), [Pydantic](https://docs.pydantic.dev) | API and data contracts | MIT |
| [NumPy](https://numpy.org) | numerics | BSD-3-Clause |
| [React](https://react.dev), [Vite](https://vite.dev) | user interface | MIT |
| [Inter, Inter Tight](https://rsms.me/inter/) via Fontsource | typefaces bundled into the UI build | SIL Open Font License 1.1 |

Each package's own license file, shipped with the package, is authoritative.
