"""Download every OCR recognizer that the release EXE supports.

PyInstaller then bundles these files from RapidOCR's package directory.  End
users never download a model at runtime and the OCR path remains fully local.
"""

from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR


LANGUAGES = (
    LangRec.LATIN,
    LangRec.ARABIC,
    LangRec.CYRILLIC,
    LangRec.DEVANAGARI,
    LangRec.JAPAN,
    LangRec.KOREAN,
    LangRec.CH,
)


def main():
    for language in LANGUAGES:
        print(f"Preparing OCR model: {language.value}")
        # Japanese is currently available as PP-OCRv4 only.  The remaining
        # supported scripts use the newer PP-OCRv5 recognizers.
        version = OCRVersion.PPOCRV4 if language == LangRec.JAPAN else OCRVersion.PPOCRV5
        RapidOCR(params={
            "Global.log_level": "warning",
            "Global.use_cls": False,
            "EngineConfig.onnxruntime.intra_op_num_threads": 1,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            "Det.lang_type": LangRec.CH,
            "Det.model_type": ModelType.MOBILE,
            "Det.ocr_version": OCRVersion.PPOCRV5,
            "Det.limit_type": "max",
            "Det.limit_side_len": 960,
            "Rec.lang_type": language,
            "Rec.model_type": ModelType.MOBILE,
            "Rec.ocr_version": version,
        })


if __name__ == "__main__":
    main()
