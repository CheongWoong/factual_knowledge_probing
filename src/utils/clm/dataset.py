import logging
from dataclasses import dataclass
from typing import Dict, Sequence
from copy import deepcopy

import torch
from torch.utils.data import Dataset

import transformers

IGNORE_INDEX = -100
DEFAULT_PAD_TOKEN = "[PAD]"
DEFAULT_EOS_TOKEN = "</s>"
DEFAULT_BOS_TOKEN = "<s>"
DEFAULT_UNK_TOKEN = "<unk>"
PROMPT_DICT = {
    "prompt_truncated": (
        " {truncated_input}"
    ),
    "prompt_full": (
        "### Input:\n {input}\n\n### Response:"
    ),
}


def tokenize_fn(strings: Sequence[str], tokenizer: transformers.PreTrainedTokenizer, block_size) -> Dict:
    """Tokenize a list of strings."""
    tokenized_list = [
        tokenizer(
            text,
            return_tensors="pt",
            # padding="longest",
            padding="max_length",
            # max_length=tokenizer.model_max_length,
            max_length=block_size,
            truncation=True,
        )
        for text in strings
    ]
    input_ids = labels = [tokenized.input_ids[0] for tokenized in tokenized_list]
    input_ids_lens = labels_lens = [
        tokenized.input_ids.ne(tokenizer.pad_token_id).sum().item() for tokenized in tokenized_list
    ]
    return dict(
        input_ids=input_ids,
        labels=labels,
        input_ids_lens=input_ids_lens,
        labels_lens=labels_lens,
    )

def preprocess(
    sources: Sequence[str],
    targets: Sequence[str],
    tokenizer: transformers.PreTrainedTokenizer,
    block_size
) -> Dict:
    """Preprocess the data by tokenizing."""
    examples = [s + ' ' + t for s, t in zip(sources, targets)]
    examples_tokenized, sources_tokenized = [tokenize_fn(strings, tokenizer, block_size) for strings in (examples, sources)]
    input_ids = examples_tokenized["input_ids"]
    labels = deepcopy(input_ids)
    for label, source_len in zip(labels, sources_tokenized["input_ids_lens"]):
        label[:source_len] = IGNORE_INDEX
    # for label in labels:
    #     label[:-1] = IGNORE_INDEX
    return dict(input_ids=input_ids, labels=labels)

class SupervisedDataset(Dataset):
    """Dataset for supervised fine-tuning."""

    def __init__(self, data, tokenizer: transformers.PreTrainedTokenizer, block_size, truncated):
        super(SupervisedDataset, self).__init__()
        logging.warning("Loading data...")
        list_data_dict = data

        logging.warning("Formatting inputs...")
        if truncated:
            prompt = PROMPT_DICT["prompt_truncated"]
        else:
            prompt = PROMPT_DICT["prompt_full"]
        sources = [
            prompt.format_map(example) for example in list_data_dict
        ]
        targets = [f"{example['output']}{tokenizer.eos_token}" for example in list_data_dict]

        logging.warning("Tokenizing inputs... This may take some time...")
        data_dict = preprocess(sources, targets, tokenizer, block_size)

        self.input_ids = data_dict["input_ids"]
        self.labels = data_dict["labels"]

    def __len__(self):
        return len(self.input_ids)

    def __getitem__(self, i) -> Dict[str, torch.Tensor]:
        return dict(input_ids=self.input_ids[i], labels=self.labels[i])
    
@dataclass
class DataCollatorForSupervisedDataset(object):
    """Collate examples for supervised fine-tuning."""

    tokenizer: transformers.PreTrainedTokenizer

    def __call__(self, instances: Sequence[Dict]) -> Dict[str, torch.Tensor]:
        input_ids, labels = tuple([instance[key] for instance in instances] for key in ("input_ids", "labels"))
        input_ids = torch.nn.utils.rnn.pad_sequence(
            input_ids, batch_first=True, padding_value=self.tokenizer.pad_token_id
        )
        labels = torch.nn.utils.rnn.pad_sequence(labels, batch_first=True, padding_value=IGNORE_INDEX)
        labels[labels == self.tokenizer.pad_token_id] = IGNORE_INDEX ## cw: this DOES matter for prompt tuning
        return dict(
            input_ids=input_ids,
            labels=labels,
            attention_mask=input_ids.ne(self.tokenizer.pad_token_id),
        )