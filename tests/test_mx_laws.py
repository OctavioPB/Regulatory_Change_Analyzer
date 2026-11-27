"""Mexican law loader and the NLP fixes found by the DOF change-detection eval — offline."""
from src.models.document import ChangeType
from src.nlp.classifier import classify_modification
from src.nlp.comparator import compare_sections
from src.nlp.regulation_id import regulation_key, title_prefilter
from src.nlp.section_splitter import split_into_sections

from evals.sources.mx_laws import article_key, capture_intervals, clean, compare, decree_articles, parse_law

RAW = """LEY DE INSTITUCIONES DE CRÉDITO
CÁMARA DE DIPUTADOS DEL H. CONGRESO DE LA UNIÓN
Secretaría General
Secretaría de Servicios Parlamentarios
Última Reforma DOF 24-01-2024
1 de 309
LEY DE INSTITUCIONES DE CRÉDITO
TEXTO VIGENTE
Artículo 48.- Las tasas de interés.
Artículo 48 Bis 1.- La Ley del Banco de México.
Artículo adicionado DOF 10-01-2014
Artículo 107 Bis. - Las Comisiones Nacionales.
Fracción reformada DOF 09-03-2018. Reformada DOF 24-01-2024
Artículo 2 79.- Los lineamientos.
TRANSITORIOS
Artículo Primero.- El presente Decreto entrará en vigor.
"""


def test_cleaning_drops_page_noise_editorial_notes_and_transitorios():
    body = clean(RAW, "LEY DE INSTITUCIONES DE CRÉDITO")
    assert "Secretaría General" not in body and "1 de 309" not in body and "Última Reforma" not in body
    assert "adicionado DOF" not in body and "Reformada DOF" not in body
    assert "entrará en vigor" not in body  # decree transitorios are not the law's articles


def test_articles_keep_bis_and_letter_suffixes_and_rejoin_split_digits():
    law = parse_law(RAW, law="LIC", on="20240127")
    assert [k for k, _ in law.articles] == ["48", "48 bis 1", "107 bis", "279"]
    assert article_key("87", " -D") == "87-d" and article_key("2 79") == "279"


def test_compare_ignores_words_split_by_the_pdf_text_layer():
    b = parse_law(RAW, law="LIC", on="b")
    a = parse_law(RAW.replace("Las Comisiones", "L as Comisiones").replace("tasas de interés", "tasas de interés y comisiones"),
                  law="LIC", on="a")
    assert compare(b, a) == {"added": [], "removed": [], "modified": ["48"]}


def test_decree_clause_lists_the_articles_of_this_law_only():
    decree = ("Artículo Segundo.- Se reforma el artículo 96 de la Ley de Protección y Defensa al Usuario de "
              "Servicios Financieros, para quedar como sigue: ... Artículo Tercero.- Se reforman los artículos "
              "107 Bis, párrafo primero; 109 Bis 1, párrafos primero y segundo; y se adicionan los artículos "
              "48 Bis 1, con un último párrafo; 2 0, de la Ley de Instituciones de Crédito, para quedar como sigue:")
    keys, clause = decree_articles(decree, "LEY DE INSTITUCIONES DE CRÉDITO")
    assert keys == ["107 bis", "109 bis 1", "48 bis 1", "20"]
    assert clause.startswith("Se reforman los artículos 107 Bis")


def test_capture_intervals_count_reforms_in_between():
    reforms = [("20240124", "a.pdf"), ("20251114", "b.pdf")]
    assert capture_intervals(["20220928120000", "20240127120000", "20240531120000"], reforms) == [
        ("20220928120000", "20240127120000", ["20240124"]), ("20240127120000", "20240531120000", [])]


# ── app fixes (src/nlp) ───────────────────────────────────────────────────────

def test_app_splits_bis_and_letter_articles_as_their_own_sections():
    # "A partir…" / "Y otro…": a one-letter word opening the text is not an article suffix
    text = ("LEY\nArtículo 48.- A partir de hoy.\nArtículo 48 Bis 1.- B.\nArtículo 17-H.- C.\n"
            "Artículo 2 79.- D.\nARTICULO 36. E.\nArtículo 87 -D.- Y otro.")
    assert list(split_into_sections(text)) == [
        "artículo 48", "artículo 48 bis 1", "artículo 17-h", "artículo 279", "articulo 36", "artículo 87-d"]


def test_app_does_not_flag_words_split_by_the_pdf():
    old = "Artículo 102.- No tengan relación con el fondo del asunto.\nArtículo 103.- Otro."
    assert compare_sections(old, old.replace("fondo", "fo ndo").replace("Otro", "O tro")) == []


def test_reference_update_is_other_and_added_fracciones_are_new_requirement():
    old = ("Para tales efectos el plazo será de diez días y se estará a lo establecido en el Código Federal de "
           "Procedimientos Civiles.")
    new = old.replace("Federal", "Nacional").replace("Civiles.", "Civiles y Familiares.")
    assert classify_modification(old, new) is ChangeType.other  # not "deadline" from the old "plazo"
    art = "Artículo 124.- Es improcedente el recurso: I. a IX. ... IX. Derogada."
    added = art + " X. Que el contribuyente manifieste desconocer el acto. " + "Y además otros supuestos. " * 12
    assert classify_modification(art, added) is ChangeType.new_requirement  # not "repeal" from "Derogada"


def test_law_titles_identify_the_law_but_mentions_do_not():
    assert regulation_key("LEY DEL MERCADO DE VALORES") == "law:ley del mercado de valores"
    assert regulation_key("CÓDIGO FISCAL DE LA FEDERACIÓN") == "law:codigo fiscal de la federacion"
    assert regulation_key("Resolución que modifica las disposiciones conforme a la Ley de Instituciones de Crédito") is None
    assert title_prefilter("law:ley de instituciones de credito") == "%_nst_t_c__n_s%cr_d_t_%"
