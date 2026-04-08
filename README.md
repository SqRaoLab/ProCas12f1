# ProCas12f1

This repository contains the training and testing code and prediction model for ProCas12f1.


## 1. Deep Learning

This folder contains the code for training and predicting with the ProCas12f1 model. The code is written in Python and uses uv for dependency management.

### 1.1 Installation

Before setting up the environment, please install uv following the official documentation.

```bash
# Python 3.10-3.12
git clone git@github.com:SqRaoLab/ProCas12f1.git
cd ProCas12f1/deep_learning

# prepare the running environment
uv sync

uv run main.py --help

Usage: main.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  design   design sgRNA by gene or fasta file
  ml       test prediction effect on multiple machine learning models
  predict  predict the editing frequency
  setup    prepare the database for web interface
  shap     calculate SHAP values to score the importance of each feature.
  start    start web interface
  train    train deep learning model
```

### 1.2 Toolkit Components

This toolkit includes:

- setup: Prepare files required for the design module and web interface

- train: Model training code

- predict: Model prediction code

- ml: Machine learning model code described in the manuscript

- shap: SHAP analysis and visualization code

- design: De novo sgRNA design

- start: Launch the web interface for sgRNA design

### 1.3 Usage Example

For more detailed usage, use uv run main.py setup --help:

```bash
uv run main.py setup --help
Usage: main.py setup [OPTIONS]

  prepare the database for web interface

Options:
  -c, --config PATH
  -i, --input-json PATH
  -h, --help             Show this message and exit.
```

## License

Please refer to the repository for licensing information.

## Citation

If you use this code in your research, please cite the corresponding manuscript.

For questions or issues, please open an issue on GitHub.
