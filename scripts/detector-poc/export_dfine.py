"""Export D-FINE-N (Apache-2.0, original repo weights) to ONNX, batch 1, 640x640."""
import sys
from pathlib import Path
import torch, torch.nn as nn
HERE = Path(__file__).resolve().parents[2] / ".scratchpad" / "yolo-poc"   # big, gitignored: venv, models, frames
sys.path.insert(0, str(HERE / "dl" / "dfine-repo"))
from src.core import YAMLConfig
cfg = YAMLConfig(str(HERE / "dl/dfine-repo/configs/dfine/dfine_hgnetv2_n_coco.yml"), resume=str(HERE / "dl/dfine_n_coco.pth"))
cfg.yaml_cfg["HGNetv2"]["pretrained"] = False
ck = torch.load(HERE / "dl/dfine_n_coco.pth", map_location="cpu")
cfg.model.load_state_dict(ck["ema"]["module"] if "ema" in ck else ck["model"])
class M(nn.Module):
    def __init__(s):
        super().__init__(); s.m = cfg.model.deploy(); s.p = cfg.postprocessor.deploy()
    def forward(s, images, sizes):
        return s.p(s.m(images), sizes)
m = M().eval()
x, sz = torch.rand(1, 3, 640, 640), torch.tensor([[640, 640]])
with torch.no_grad():
    m(x, sz)
    torch.onnx.export(m, (x, sz), str(HERE / "models/dfine-n-640.onnx"), input_names=["images", "orig_target_sizes"],
                      output_names=["labels", "boxes", "scores"], opset_version=17, do_constant_folding=True, dynamo=False)
print("exported")
