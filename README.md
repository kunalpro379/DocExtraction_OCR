# Document Extraction System

A clean, modular 4-layer OOP architecture for document extraction using interchangeable AI models (OCR, LLM, Document Intelligence).

## Architecture

```
DocumentSystem/
│
├── main.py                    # Application bootstrap
│
├── config/                    # Configuration layer
│   ├── settings.py           # Model selection and system settings
│   └── registry.py           # Model registration and resolution
│
├── models/                    # Models layer
│   ├── base.py               # Base interfaces (BaseOCR, BaseLLM, BaseDocument, etc.)
│   ├── ocr.py                # OCR implementations (GLMOCR, AzureOCR, UnlimitedOCR)
│   ├── llm.py                # LLM implementations (OpenAI, Gemini)
│   ├── adi.py                # Document Intelligence implementations
│   └── documents.py          # Document types (Agreement, Invoice, PAN, Aadhaar)
│
├── services/                  # Services layer
│   ├── extraction.py         # Data extraction orchestration
│   ├── validation.py         # Data validation logic
│   ├── processing.py         # Document processing pipeline
│   └── database.py           # Data persistence
│
└── utils/                     # Utilities layer
    ├── logger.py             # Logging utilities
    └── helpers.py            # Common helper functions
```

## Key Design Principles

- **Dependency Injection**: Documents use injected models, not inheritance
- **Model Interchangeability**: Change models via config, no code changes needed
- **SOLID Principles**: Single responsibility, dependency inversion, etc.
- **Composition over Inheritance**: Documents use models, don't extend them
- **Loose Coupling**: Components interact through interfaces

## Input Folder Structure

```
Input/
├── agreement/
│   └── files/
│       ├── agreement1.pdf
│       └── agreement2.pdf
├── invoice/
│   └── files/
│       ├── invoice1.pdf
│       └── invoice2.pdf
├── pan/
│   └── files/
│       └── pan1.pdf
└── aadhaar/
    └── files/
        └── aadhaar1.pdf
```

## Configuration

Edit `config.json` to change model selection:

```json
{
  "models": {
    "ocr": "glm",              // Options: glm, azure, unlimited
    "llm": "openai",           // Options: openai, gemini
    "document_intelligence": "azure"  // Options: azure
  }
}
```

## Usage

### Install dependencies

```bash
pip install -r requirements.txt
```

### Process all documents

```bash
python main.py full
```

### Process a single file

```bash
python main.py file --input path/to/document.pdf
```

### Process with specific document type

```bash
python main.py file --input path/to/document.pdf --type invoice
```

### Re-process already extracted data

```bash
python main.py reprocess --name document_name --type agreement
```

### Show system statistics

```bash
python main.py stats
```

### Debug mode

```bash
python main.py full --log-level DEBUG
```

## Adding New Models

### Add a new OCR model

1. Create class in `models/ocr.py` inheriting from `BaseOCR`
2. Register in `config/registry.py`:

```python
from models.ocr import NewOCR
registry.register_ocr("new_ocr", NewOCR)
```

3. Update `config.json` to use it: `"ocr": "new_ocr"`

### Add a new document type

1. Create class in `models/documents.py` inheriting from `BaseDocument`
2. Register in `config/registry.py`:

```python
from models.documents import NewDocument
registry.register_document("new_document", NewDocument)
```

## Features

- **Multi-model support**: GLM OCR, Azure OCR, Unlimited OCR, OpenAI, Gemini, Azure ADI
- **Multiple document types**: Agreement, Invoice, PAN, Aadhaar
- **Automatic validation**: PAN/Aadhaar format validation, email/phone validation
- **Data persistence**: SQLite database with export capabilities
- **Comprehensive logging**: File and console logging with performance tracking
- **Batch processing**: Process entire folder structures
- **Multiple output formats**: JSON, CSV, Markdown, plain text

## Services

- **ExtractionService**: Orchestrates data extraction using registered models
- **ValidationService**: Validates extracted data with field-specific rules
- **ProcessingService**: Manages the complete document processing pipeline
- **DatabaseService**: Handles data persistence and retrieval

## Document Model Relationship

Documents use models through dependency injection:

```python
# Document doesn't inherit from OCR
agreement = Agreement(
    ocr_model=ocr_instance,      # Injected
    llm_model=llm_instance,      # Injected
    adi_model=adi_instance       # Injected
)
```

This allows any document to use any registered model without code changes.

## License

MIT License