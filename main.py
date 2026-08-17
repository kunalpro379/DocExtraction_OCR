"""
Main - Application bootstrap and entry point.
Initializes the system and starts the document processing pipeline.
"""

import sys
import argparse
from config import settings, registry, register_models
from services import processing_service, database_service
from utils.logger import get_logger, set_global_log_level


def initialize_system():
    """
    Initialize the document extraction system.
    - Load settings
    - Register all available models
    - Initialize services
    """
    logger = get_logger(__name__)
    
    try:
        logger.info("Initializing Document Extraction System...")
        
        # Load settings
        logger.info(f"Loading settings from {settings.config_path}")
        logger.info(f"OCR Model: {settings.get_ocr_model()}")
        logger.info(f"LLM Model: {settings.get_llm_model()}")
        logger.info(f"ADI Model: {settings.get_document_intelligence_model()}")
        
        # Register all models
        logger.info("Registering models...")
        register_models()
        
        logger.info(f"Available OCR models: {registry.list_ocr_models()}")
        logger.info(f"Available LLM models: {registry.list_llm_models()}")
        logger.info(f"Available ADI models: {registry.list_adi_models()}")
        logger.info(f"Available document types: {registry.list_document_models()}")
        
        # Initialize database
        logger.info("Initializing database...")
        # Database is initialized automatically in DatabaseService constructor
        
        logger.info("System initialization complete.")
        return True
        
    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        return False


def run_full_processing(input_path: str = None):
    """
    Run full document processing on the input folder.
    
    Args:
        input_path: Optional custom input path
    """
    logger = get_logger(__name__)
    
    try:
        logger.info("Starting full document processing...")
        
        # Process all documents in the input folder
        results = processing_service.process_input_folder(input_path)
        
        # Print summary
        print("\n" + "=" * 50)
        print("PROCESSING SUMMARY")
        print("=" * 50)
        print(f"Total Processed: {results['processed']}")
        print(f"Total Failed: {results['failed']}")
        
        if results['document_types']:
            print("\nBy Document Type:")
            for doc_type, type_result in results['document_types'].items():
                print(f"  {doc_type}: {type_result['processed']} processed, {type_result['failed']} failed")
        
        if results['errors']:
            print("\nErrors:")
            for error in results['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(results['errors']) > 10:
                print(f"  ... and {len(results['errors']) - 10} more errors")
        
        print("=" * 50)
        
        # Get database statistics
        stats = database_service.get_statistics()
        print("\nDATABASE STATISTICS")
        print("=" * 50)
        print(f"Total Documents: {stats['total_documents']}")
        print(f"By Type: {stats['by_type']}")
        print(f"Validation Status: {stats['validation_status']}")
        print("=" * 50)
        
        logger.info("Full processing complete.")
        
    except Exception as e:
        logger.error(f"Full processing failed: {e}")
        print(f"Error: {e}")
        sys.exit(1)


def run_single_file(file_path: str, document_type: str = None):
    """
    Process a single document file.
    
    Args:
        file_path: Path to the document file
        document_type: Optional document type override
    """
    logger = get_logger(__name__)
    
    try:
        logger.info(f"Processing single file: {file_path}")
        
        result = processing_service.process_single_file(file_path, document_type)
        
        print("\n" + "=" * 50)
        print("FILE PROCESSING RESULT")
        print("=" * 50)
        print(f"File: {file_path}")
        print(f"Document Type: {result.get('document_type', 'unknown')}")
        print(f"Status: {'Success' if result['success'] else 'Failed'}")
        
        if result['success']:
            print(f"Valid: {result.get('is_valid', False)}")
            if result.get('validation_errors'):
                print("Validation Errors:")
                for error in result['validation_errors']:
                    print(f"  - {error}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        print("=" * 50)
        
        logger.info("Single file processing complete.")
        
    except Exception as e:
        logger.error(f"Single file processing failed: {e}")
        print(f"Error: {e}")
        sys.exit(1)


def run_reprocess(document_name: str, document_type: str):
    """
    Re-process an already extracted document.
    
    Args:
        document_name: Name of the document (without extension)
        document_type: Type of document
    """
    logger = get_logger(__name__)
    
    try:
        logger.info(f"Re-processing document: {document_name}")
        
        result = processing_service.reprocess_extracted_data(document_name, document_type)
        
        print("\n" + "=" * 50)
        print("RE-PROCESSING RESULT")
        print("=" * 50)
        print(f"Document: {document_name}")
        print(f"Document Type: {document_type}")
        print(f"Status: {'Success' if result['success'] else 'Failed'}")
        
        if result['success']:
            print(f"Valid: {result.get('is_valid', False)}")
            if result.get('validation_errors'):
                print("Validation Errors:")
                for error in result['validation_errors']:
                    print(f"  - {error}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        print("=" * 50)
        
        logger.info("Re-processing complete.")
        
    except Exception as e:
        logger.error(f"Re-processing failed: {e}")
        print(f"Error: {e}")
        sys.exit(1)


def show_statistics():
    """Show system statistics."""
    logger = get_logger(__name__)
    
    try:
        # Get processing summary
        processing_summary = processing_service.get_processing_summary()
        
        # Get database statistics
        db_stats = database_service.get_statistics()
        
        print("\n" + "=" * 50)
        print("SYSTEM STATISTICS")
        print("=" * 50)
        
        print("\nFile Processing:")
        print(f"  Total Processed: {processing_summary['total_processed']}")
        print(f"  Valid: {processing_summary['valid_count']}")
        print(f"  Invalid: {processing_summary['invalid_count']}")
        
        if processing_summary['by_type']:
            print("  By Type:")
            for doc_type, count in processing_summary['by_type'].items():
                print(f"    {doc_type}: {count}")
        
        print("\nDatabase:")
        print(f"  Total Documents: {db_stats['total_documents']}")
        print(f"  By Type: {db_stats['by_type']}")
        print(f"  Validation Status: {db_stats['validation_status']}")
        
        print("\nConfiguration:")
        print(f"  OCR Model: {settings.get_ocr_model()}")
        print(f"  LLM Model: {settings.get_llm_model()}")
        print(f"  ADI Model: {settings.get_document_intelligence_model()}")
        print(f"  Input Directory: {settings.get_input_dir()}")
        print(f"  Output Directory: {settings.get_output_dir()}")
        
        print("\nAvailable Models:")
        print(f"  OCR: {registry.list_ocr_models()}")
        print(f"  LLM: {registry.list_llm_models()}")
        print(f"  ADI: {registry.list_adi_models()}")
        print(f"  Documents: {registry.list_document_models()}")
        
        print("=" * 50)
        
    except Exception as e:
        logger.error(f"Failed to show statistics: {e}")
        print(f"Error: {e}")


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description="Document Extraction System - Extract data from documents using AI models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all documents in Input folder
  python main.py full
  
  # Process all documents in custom folder
  python main.py full --input /path/to/input
  
  # Process a single file
  python main.py file --input /path/to/document.pdf
  
  # Process a single file with specific document type
  python main.py file --input /path/to/document.pdf --type invoice
  
  # Re-process an already extracted document
  python main.py reprocess --name my_document --type agreement
  
  # Show system statistics
  python main.py stats
  
  # Use different log level
  python main.py full --log-level DEBUG
        """
    )
    
    # Mode subcommands
    subparsers = parser.add_subparsers(dest='mode', help='Processing mode')
    
    # Full processing mode
    full_parser = subparsers.add_parser('full', help='Process all documents in input folder')
    full_parser.add_argument('--input', help='Custom input directory path')
    
    # Single file mode
    file_parser = subparsers.add_parser('file', help='Process a single document file')
    file_parser.add_argument('--input', required=True, help='Path to the document file')
    file_parser.add_argument('--type', help='Document type (auto-detected if not specified)')
    
    # Re-process mode
    reprocess_parser = subparsers.add_parser('reprocess', help='Re-process an already extracted document')
    reprocess_parser.add_argument('--name', required=True, help='Document name (without extension)')
    reprocess_parser.add_argument('--type', required=True, help='Document type')
    
    # Statistics mode
    stats_parser = subparsers.add_parser('stats', help='Show system statistics')
    
    # Global options
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Set logging level')
    
    args = parser.parse_args()
    
    # Set log level
    set_global_log_level(args.log_level)
    logger = get_logger(__name__)
    
    # Initialize system
    if not initialize_system():
        logger.error("System initialization failed. Exiting.")
        sys.exit(1)
    
    # Execute based on mode
    if args.mode == 'full':
        run_full_processing(args.input)
    elif args.mode == 'file':
        run_single_file(args.input, args.type)
    elif args.mode == 'reprocess':
        run_reprocess(args.name, args.type)
    elif args.mode == 'stats':
        show_statistics()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
