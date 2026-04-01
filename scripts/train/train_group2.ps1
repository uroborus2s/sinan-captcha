param(
    [string]$DatasetYaml = "datasets/group2/v1/yolo/dataset.yaml",
    [string]$ProjectDir = "runs/group2",
    [string]$Name = "v1",
    [string]$Model = "yolo26n.pt"
)

uv run python -m core.train.group2.cli --dataset-yaml $DatasetYaml --project $ProjectDir --name $Name --model $Model
