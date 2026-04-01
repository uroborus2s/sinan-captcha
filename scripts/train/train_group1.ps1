param(
    [string]$DatasetYaml = "datasets/group1/v1/yolo/dataset.yaml",
    [string]$ProjectDir = "runs/group1",
    [string]$Name = "v1",
    [string]$Model = "yolo26n.pt"
)

uv run python -m core.train.group1.cli --dataset-yaml $DatasetYaml --project $ProjectDir --name $Name --model $Model
