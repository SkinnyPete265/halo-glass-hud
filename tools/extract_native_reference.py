"""Capture the previously tested native input/DRS components as build inputs."""
from pathlib import Path
import argparse
from project_config import local_settings
import copy
import hashlib
import json
import re
from compression import zstd
from formats import erpw, idf, pkg, uinode

ROOT = Path(__file__).resolve().parents[1]
erpw.zstd_d = zstd.decompress
erpw.zstd_c = lambda data: zstd.compress(data, options={
    zstd.CompressionParameter.compression_level: 8,
    zstd.CompressionParameter.window_log: 20,
    zstd.CompressionParameter.content_size_flag: 1,
})

def walk(node):
    if uinode.is_node(node):
        yield node
    if isinstance(node, pkg.Obj):
        for key, child in node.items:
            yield from walk(child)
    elif isinstance(node, pkg.Arr):
        for child in node.items:
            yield from walk(child)

def strings(node):
    if isinstance(node,pkg.Val) and node.type=="stri":
        yield node.value
    elif isinstance(node,pkg.Obj):
        for key,child in node.items:
            yield from strings(child)
    elif isinstance(node,pkg.Arr):
        for child in node.items:
            yield from strings(child)

def main():
    settings = local_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-addon', type=Path, default=settings.get('legacy_addon'))
    parser.add_argument('--stock-archive', type=Path, default=settings.get('stock_archive'))
    args = parser.parse_args()
    if args.legacy_addon is None or args.stock_archive is None:
        parser.error('Supply --legacy-addon and --stock-archive, or configure their local paths.')
    stock = erpw.Erp(args.stock_archive)
    additional = erpw.Erp(args.legacy_addon/"assets/halo-new-resources.erpk")
    if stock.ver != additional.ver:
        raise ValueError("Reference ERP versions differ")
    base = {r.name:r for r in stock.res}
    extra = {r.name:r for r in additional.res}
    operations = json.loads((args.legacy_addon/"erp/halo-hud.json").read_text())["ops"]
    replacements = {(o["resource"],o["fragment"]):args.legacy_addon/o["source"]
                    for o in operations if o["op"]=="replace-resource"}

    def resource(name):
        proto = extra[name] if name in extra else base[name]
        result = copy.deepcopy(proto)
        for index in range(len(result.frags)):
            override = replacements.get((name,index))
            if override:
                stock.set_frag(result,index,override.read_bytes())
        return result

    directory = "eaid://ui_package/art/osd/components/dial/"
    seeds = {
        directory+"engine_meters.idf",
        directory+"engine_meters.emb?context=default",
        directory+"engine_meters.idf?context=animstringtable&file=0",
        directory+"engine_meters.idf/brake_slider_null?context=animation",
        directory+"engine_meters.idf/accelerate_slider_null?context=animation",
        directory+"dial_pit_lane_slider.emb?context=default",
        directory+"dial_complete.idf/speedo_number?context=animation",
        "eaid://ui_package/art/osd/local_halo/status.idf",
    }
    selected = {}
    pending = list(seeds)
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        current = resource(name)
        if name.endswith("/status.idf"):
            scene = idf.Idf(stock.frag_data(current,0))
            children = scene.scenes[0].root.obj["children"]
            children.items = [child for child in children.items
                              if child["name"].value != "halo_drs_open"]
            idf.relookup(scene.scenes[0].entry)
            stock.set_frag(current,0,scene.to_bytes())
        selected[name] = current
        references = set()
        for index in range(len(current.frags)):
            data = stock.frag_data(current,index)
            if data.startswith(b"!pkg"):
                references.update(s for s in strings(pkg.Pkg(data).root)
                                  if s.startswith("eaid://"))
            else:
                references.update(s.decode() for s in re.findall(
                    rb"eaid://[A-Za-z0-9_./?=&%:+-]+",data))
        for reference in references:
            pending.extend(key for key in extra if key.startswith(reference))

    output = ROOT/"native/reference"
    archive = copy.copy(stock)
    archive.res = [selected[key] for key in sorted(selected)]
    archive.to_file(output/"native-controls.erpk",reframe=False)
    template_name = "eaid://ui_package/templates/hud_dynamic_templates.ui"
    template = pkg.Pkg(replacements[(template_name,0)].read_bytes())
    f1 = next(node for node in walk(template.root)
              if uinode.name(node)=="hud_f1_dial")
    drs = next(node for node in walk(f1)
               if uinode.name(node)=="drs_and_pit_distance")
    fragment = pkg.Pkg()
    fragment.name = template.name
    fragment.root = copy.deepcopy(drs)
    (output/"drs-template.bin").write_bytes(fragment.to_bytes())
    provenance = {"source_addon":"local.halo-hud v0.31.0",
                  "resources":list(sorted(selected)),
                  "stock_archive_sha256":hashlib.sha256(args.stock_archive.read_bytes()).hexdigest()}
    (output/"native-controls-source.json").write_text(
        json.dumps(provenance,indent=2)+"\n",encoding="utf-8")
    print(f"Captured {len(selected)} native component resources and the DRS template.")

if __name__=="__main__":
    main()
