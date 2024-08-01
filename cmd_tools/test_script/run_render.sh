set RPR_BLENDER_DEBUG=0

clear
# install necessary libraries
python3.11 -m pip install python-dotenv opencv-python scikit-image

clear

python3.11 cmd_render.py final_render.py