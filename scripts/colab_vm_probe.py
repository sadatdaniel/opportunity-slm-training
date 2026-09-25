import glob, os, json
out = {
    "summarizer_dirs": glob.glob("/content/repo/models/summarizer/*"),
    "classifier_dirs": glob.glob("/content/repo/models/classifier/*"),
    "manifests": sorted(os.path.basename(p) for p in glob.glob("/content/repo/experiments/manifests/*.yaml")),
    "runs": sorted(os.path.basename(p) for p in glob.glob("/content/repo/runs/*")),
}
print(json.dumps(out, indent=1))
