pip uninstall -q parlai -y
cd ParlAI
pip install .
python3 projects/image_chat/interactive.py \
    -mf models:image_chat/transresnet_multimodal/model