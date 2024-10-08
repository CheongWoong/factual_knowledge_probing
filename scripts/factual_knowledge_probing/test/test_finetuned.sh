model_type=$1
model_name_or_path=$2
dataset_name=$3
dataset_type=$4
model_name=$(basename $model_name_or_path)
out_dir=$model_name

nohup python -m "src.factual_knowledge_probing.run_"$model_type \
    --model_name_or_path $model_name_or_path \
    --do_train False \
    --do_eval True \
    --validation_file "./data/"$dataset_name"/"$dataset_type".json" \
    --per_device_train_batch_size 128 \
    --per_device_eval_batch_size 128 \
    --gradient_accumulation_steps 1 \
    --gradient_checkpointing True \
    --fp16 True \
    --learning_rate 2e-5 \
    --num_train_epochs 3 \
    --block_size 128 \
    --save_strategy no \
    --seed 0 \
    --report_to tensorboard \
    --output_dir "results/"$out_dir \
    --truncated_prompt False \
    > "results/logs/log."$out_dir".test_"$dataset_name"_"$dataset_type &