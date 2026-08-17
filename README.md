# Document Extraction System

A clean architecture for document extraction using interchangeable AI models (OCR, LLM, Document Intelligence).

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
