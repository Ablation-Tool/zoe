import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "neurogarden_library", Path(__file__).parents[1] / "examples" / "neurogarden_library.py"
)
library = importlib.util.module_from_spec(spec)
spec.loader.exec_module(library)


def write(path, text):
    path.write_text(text, encoding="utf-8")


def test_title_subtitle_and_toc_are_cataloged_without_prose(tmp_path):
    book = tmp_path / "Biomedical Imaging (Elsevier)"
    book.mkdir()
    write(book / "001_Title_page.html", "<h1>Biomedical Imaging</h1><h2>Applications and Advances</h2>")
    write(book / "002_toc.html", '<a href="c02.xhtml">Chapter 2: Evaluation of Tomographic Data</a>')
    write(book / "003_c02.html", "<p>Chapter prose must not enter the metadata catalog.</p>")
    record = library.catalog_book(book)
    assert record["title"] == "Biomedical Imaging Applications and Advances"
    assert record["folder_title_matches"] is True
    assert record["toc"][0]["text"].startswith("Chapter 2")
    assert "prose" not in str(record)
    assert record["citation_scope"].startswith("reference-only")


def test_intentional_folder_title_mismatch_is_preserved(tmp_path):
    book = tmp_path / "De Gruyter Handbook of Mathematical Methods in Medical and Biological Sciences"
    book.mkdir()
    write(book / "003_titlepage.html", "<h1>De Gruyter Handbook of Humor Studies</h1>")
    write(book / "005_toc.html", '<a href="humor.xhtml">The Neuroscience of Humor</a>')
    record = library.catalog_book(book)
    assert record["title"] == "De Gruyter Handbook of Humor Studies"
    assert record["folder_title_matches"] is False
    assert record["intentional"] is True
    assert record["subjects"] == ["creativity", "communication", "neuroscience-of-humor"]
    assert "intentional collection entry preserved" in record["warning"]
