from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_DIR = str(Path(__file__).parent / "EXAONE-3.5-7.8B-Instruct-AWQ")

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    trust_remote_code=True,
    torch_dtype=torch.float16,
    device_map="cuda",
)

messages = [
    {"role": "user", "content": "너의 모델명, 파라미터 크기, 개발사를 한 문장으로 소개하고, 3 곱하기 7은 얼마인지 알려줘."}
]
input_ids = tokenizer.apply_chat_template(
    messages, add_generation_prompt=True, return_tensors="pt"
).to(model.device)

output = model.generate(
    input_ids,
    max_new_tokens=200,
    do_sample=False,
)

print(tokenizer.decode(output[0][input_ids.shape[-1] :], skip_special_tokens=True))
