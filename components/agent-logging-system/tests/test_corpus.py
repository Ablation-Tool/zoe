import json

import pytest

from agent_logging_system.corpus import build, load_reviews


def write_book(root, folder, files):
    book = root / folder
    book.mkdir()
    for name, text in files.items():
        (book / name).write_text(text, encoding="utf-8")
    return book


def test_extracts_chapters_without_claiming_understanding(tmp_path):
    write_book(tmp_path, "Imaging", {
        "001_toc.html": '<a href="c02.xhtml">Chapter 2</a>',
        "001_biocoder_signup_page.html": '<img alt="Signup" src="signup.png">',
        "014_author_bios.html": "<h2>About the Author</h2><p>Publisher biography.</p>",
        "007_c02.html": "<h1>Evaluation of Tomographic Data</h1><p>Voxel size is not resolution.</p>" + "x" * 1000,
        "008_c03.html": "<h1>Radiation Exposure</h1><p>Dose area product.</p>",
    })
    document = build(tmp_path)
    assert document["coverage"]["present_books"] == 1
    assert document["coverage"]["missing_books"] == 34
    assert document["coverage"]["chapters"] == 2
    assert document["coverage"]["understood"] is False
    chapter = document["books"][0]["chapters"][0]
    assert chapter["title"] == "Evaluation of Tomographic Data"
    assert chapter["index_terms"]["sampling"] == 1
    assert "x" * 500 not in json.dumps(document)
    assert len(chapter["snippet"]) <= 280
    assert chapter["snippet"]


def test_review_requires_hashes_concepts_application_limitations_and_use(tmp_path):
    book = write_book(tmp_path, "Imaging", {
        "007_c02.html": "<h1>Tomography</h1><p>Voxel size is not resolution.</p>",
    })
    source = "Imaging/007_c02.html"
    digest = __import__("agent_logging_system.corpus", fromlist=["sha256"]).sha256(book / "007_c02.html")
    review = {
        source: {
            "source_sha256": digest,
            "concepts": ["voxel size differs from resolution"],
            "application": "sampling review",
            "limitations": "synthetic teaching only",
            "use": "assess_sampling",
            "reviewed_at": "2026-11-08T00:00:00Z",
        }
    }
    document = build(tmp_path, review)
    assert document["coverage"]["chapters"] == 1
    assert document["coverage"]["reviewed_chapters"] == 1
    review_path = tmp_path / "reviews.json"
    review_path.write_text(json.dumps({"schema": "neurogarden-reviews-v1", "reviews": review}))
    document = build(tmp_path, load_reviews(review_path))
    assert document["coverage"]["reviewed_chapters"] == 1
    del review[source]["use"]
    review[source].pop("no_tool_rationale", None)
    with pytest.raises(ValueError, match="needs use or no-tool rationale"):
        build(tmp_path, review)
    review[source]["use"] = "assess_sampling"
    review[source]["source_sha256"] = "changed"
    with pytest.raises(ValueError, match="source changed"):
        build(tmp_path, review)


def test_empty_directories_remain_explicit(tmp_path):
    (tmp_path / "waiting").mkdir()
    document = build(tmp_path)
    assert document["books"][0]["status"] == "waiting-for-content"
    assert document["coverage"]["chapters"] == 0
    assert document["coverage"]["understood"] is False


def test_gpt3_artifacts_are_excluded_with_provenance(tmp_path):
    artifacts = {
        "001_nav.html": "navigation",
        "002_xhtml-0-0.html": "title page",
        "003_xhtml-0-1.html": "copyright",
        "004_xhtml-0-2.html": "dedication",
        "005_xhtml-0-3.html": "praise",
        "007_xhtml-0-5.html": "contents",
        "015_xhtml-0-13.html": "acknowledgements",
        "016_xhtml-0-14.html": "author biography",
        "017_xhtml-0-15.html": "author biography",
    }
    files = {name: f"<p>{reason}</p>" for name, reason in artifacts.items()}
    files.update({
        "006_xhtml-0-4.html": "<p>Preface</p>",
        "008_xhtml-0-6.html": "<p>Chapter 1</p>",
        "009_xhtml-0-7.html": "<p>Chapter 2</p>",
    })
    write_book(tmp_path, "GPT-3", files)
    document = build(tmp_path)
    book = document["books"][0]
    assert len(book["chapters"]) == 3
    assert len(book["excluded_artifacts"]) == 9
    assert {item["reason"] for item in book["excluded_artifacts"]} == set(artifacts.values())
    assert all(item["source"].startswith("GPT-3/") for item in book["excluded_artifacts"])
    assert document["coverage"]["chapters"] == 3


def test_matlab_artifacts_are_excluded_with_provenance(tmp_path):
    artifacts = {
        "003_9781484203477_FM_6_Contents_at_a_Glance.html": "contents at a glance",
        "004_9781484203477_FM_5_Contents.html": "contents",
        "005_9781484203477_FM_3_About_the_Author.html": "author biography",
        "006_9781484203477_FM_4_Preface.html": "also available",
    }
    files = {name: f"<p>{reason}</p>" for name, reason in artifacts.items()}
    files.update({
        "007_9781484203477_FM_7_Introduction.html": "<p>Introduction</p>",
        "008_9781484203477_Ch01.html": "<p>Chapter 1</p>",
    })
    write_book(tmp_path, "MATLAB Numerical Calculations", files)
    document = build(tmp_path)
    book = document["books"][0]
    assert len(book["chapters"]) == 2
    assert len(book["excluded_artifacts"]) == 4
    assert {item["reason"] for item in book["excluded_artifacts"]} == set(artifacts.values())
    assert all(item["source"].startswith("MATLAB Numerical Calculations/") for item in book["excluded_artifacts"])
