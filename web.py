# LoreMasterBot web entry point.
#
# Running `python web.py` validates credentials and launches the 8bitcn-ui
# styled Gradio Search-to-Chat interface from src.web.
from src.web import launch_web


if __name__ == "__main__":
    launch_web()
