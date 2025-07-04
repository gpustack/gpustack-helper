from typing import Optional, Dict
import os
from PySide6.QtCore import QObject, QTranslator, QLocale, Signal
from PySide6.QtWidgets import QApplication
from gpustack_helper.defaults import translation_path
import logging

logger = logging.getLogger(__name__)


class TranslationManager(QObject):
    current_translator: Optional[str]
    translators: Dict[str, QTranslator]
    retranslate_signal = Signal()
    app: QApplication

    def __init__(self, parent: QApplication):
        super().__init__(parent)
        self.app = parent
        self.current_translator = None

        self.translators: Dict[str, QTranslator] = {
            "zh_CN": QTranslator(),
            "en_US": QTranslator(),
        }
        for locale, translator in self.translators.items():
            qm_path = os.path.join(translation_path, locale + ".qm")
            if os.path.exists(qm_path):
                translator.load(qm_path)
            else:
                logger.warning(
                    f"Translation file {qm_path} does not exist. Skipping loading."
                )
        # set current_locale to system locale in reload
        self.check_and_reload_locale()

    def check_and_reload_locale(self):
        preferred_list = QLocale().uiLanguages()
        for locale in preferred_list:
            system_locale = QLocale(locale).name()
            if system_locale not in self.translators:
                continue
            current_translator = self.translators.get(self.current_translator, None)
            if (
                current_translator is not None
                and self.current_translator == system_locale
            ):
                return
            self.current_translator = system_locale
            if current_translator:
                self.app.removeTranslator(current_translator)
            translator = self.translators.get(system_locale)
            if translator:
                self.app.installTranslator(translator)
            self.retranslate_signal.emit()
            break


translator: TranslationManager


def init_translator(app: QApplication) -> TranslationManager:
    """
    Initialize the translation manager and install the appropriate translator based on system locale.
    """
    global translator
    translator = TranslationManager(app)
    return translator


def get_translator() -> TranslationManager:
    """
    Get the global translator instance.
    """
    global translator
    if translator is None:
        raise RuntimeError(
            "Translator has not been initialized. Call init_translator first."
        )
    return translator
