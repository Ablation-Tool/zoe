use anyhow::Result;
use clap::{Parser, Subcommand};
use rayon::prelude::*;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

// ─── Signature schema ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum IndicatorType {
    Regex,
    String,
    FilePath,
}

#[derive(Debug, Clone, Deserialize)]
struct Indicator {
    #[serde(rename = "type")]
    kind: IndicatorType,
    pattern: String,
}

#[derive(Debug, Clone, Deserialize)]
struct Signature {
    id: String,
    name: String,
    #[allow(dead_code)]
    version: String,
    category: String,
    model_family: String,
    confidence: String,
    description: String,
    #[serde(default)]
    technique: String,
    #[serde(default)]
    match_all: bool,
    indicators: Vec<Indicator>,
    #[serde(default)]
    #[allow(dead_code)]
    tags: Vec<String>,
}

// ─── Findings ────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
struct Finding {
    id: String,
    name: String,
    category: String,
    model_family: String,
    confidence: String,
    description: String,
    technique: String,
    indicators_matched: Vec<String>,
    file: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    line: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    context: Option<String>,
}

#[derive(Debug, Serialize)]
struct ScanResult {
    target: String,
    signatures_loaded: usize,
    findings_count: usize,
    findings: Vec<Finding>,
}

// ─── Signature loading ────────────────────────────────────────────────────────

fn load_signatures_from_dir(dir: &Path) -> Vec<Signature> {
    let mut sigs = Vec::new();
    if !dir.exists() {
        return sigs;
    }
    for entry in WalkDir::new(dir).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("yaml") {
            continue;
        }
        let content = match fs::read_to_string(path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        for doc in content.split("\n---\n") {
            let doc = doc.trim();
            if doc.is_empty() {
                continue;
            }
            match serde_yaml::from_str::<Signature>(doc) {
                Ok(sig) => sigs.push(sig),
                Err(e) => eprintln!("spectral: warning: {}: {}", path.display(), e),
            }
        }
    }
    sigs
}

// Bundled signatures -- embedded at compile time so binary works standalone
const BUNDLED: &[(&str, &str)] = &[
    ("code/claude_code.yaml",                    include_str!("../signatures/code/claude_code.yaml")),
    ("code/copilot.yaml",                        include_str!("../signatures/code/copilot.yaml")),
    ("code/openai_codex.yaml",                   include_str!("../signatures/code/openai_codex.yaml")),
    ("code/cursor_windsurf.yaml",                include_str!("../signatures/code/cursor_windsurf.yaml")),
    ("code/aider.yaml",                          include_str!("../signatures/code/aider.yaml")),
    ("code/ide_tools_extended.yaml",             include_str!("../signatures/code/ide_tools_extended.yaml")),
    ("code/ide_tools_v2.yaml",                   include_str!("../signatures/code/ide_tools_v2.yaml")),
    ("agentic/claude_agent.yaml",                include_str!("../signatures/agentic/claude_agent.yaml")),
    ("agentic/autogpt_langchain.yaml",           include_str!("../signatures/agentic/autogpt_langchain.yaml")),
    ("agentic/llamaindex_semantic_kernel.yaml",  include_str!("../signatures/agentic/llamaindex_semantic_kernel.yaml")),
    ("agentic/opendevin_haystack.yaml",          include_str!("../signatures/agentic/opendevin_haystack.yaml")),
    ("agentic/agent_frameworks_v2.yaml",         include_str!("../signatures/agentic/agent_frameworks_v2.yaml")),
    ("agentic/finetuning_mlops.yaml",            include_str!("../signatures/agentic/finetuning_mlops.yaml")),
    ("agentic/serving_mlops.yaml",               include_str!("../signatures/agentic/serving_mlops.yaml")),
    ("infrastructure/api_headers.yaml",          include_str!("../signatures/infrastructure/api_headers.yaml")),
    ("infrastructure/google_gemini.yaml",        include_str!("../signatures/infrastructure/google_gemini.yaml")),
    ("infrastructure/azure_openai.yaml",         include_str!("../signatures/infrastructure/azure_openai.yaml")),
    ("infrastructure/bedrock_mistral.yaml",      include_str!("../signatures/infrastructure/bedrock_mistral.yaml")),
    ("infrastructure/inference_providers.yaml",  include_str!("../signatures/infrastructure/inference_providers.yaml")),
    ("infrastructure/model_servers.yaml",        include_str!("../signatures/infrastructure/model_servers.yaml")),
    ("infrastructure/cloud_ai_providers.yaml",   include_str!("../signatures/infrastructure/cloud_ai_providers.yaml")),
    ("infrastructure/vector_embedding_clients.yaml", include_str!("../signatures/infrastructure/vector_embedding_clients.yaml")),
    ("infrastructure/ai_gateways.yaml",          include_str!("../signatures/infrastructure/ai_gateways.yaml")),
    ("content/ai_writing.yaml",                  include_str!("../signatures/content/ai_writing.yaml")),
    ("content/ai_code_markers.yaml",             include_str!("../signatures/content/ai_code_markers.yaml")),
    ("security/prompt_injection.yaml",           include_str!("../signatures/security/prompt_injection.yaml")),
    ("security/shadow_ai.yaml",                  include_str!("../signatures/security/shadow_ai.yaml")),
    ("security/agentic_risk.yaml",               include_str!("../signatures/security/agentic_risk.yaml")),
    ("security/canary_tokens.yaml",              include_str!("../signatures/security/canary_tokens.yaml")),
    ("security/attacker_staging.yaml",           include_str!("../signatures/security/attacker_staging.yaml")),
    ("security/crypto_weakness.yaml",            include_str!("../signatures/security/crypto_weakness.yaml")),
    ("security/privilege_escalation.yaml",       include_str!("../signatures/security/privilege_escalation.yaml")),
    ("security/process_injection.yaml",          include_str!("../signatures/security/process_injection.yaml")),
];

fn load_bundled_signatures() -> Vec<Signature> {
    let mut sigs = Vec::new();
    for (name, content) in BUNDLED {
        for doc in content.split("\n---\n") {
            let doc = doc.trim();
            if doc.is_empty() {
                continue;
            }
            match serde_yaml::from_str::<Signature>(doc) {
                Ok(sig) => sigs.push(sig),
                Err(e) => eprintln!("spectral: warning: {}: {}", name, e),
            }
        }
    }
    sigs
}

fn load_signatures(custom_dir: Option<&Path>) -> Vec<Signature> {
    match custom_dir {
        Some(dir) => load_signatures_from_dir(dir),
        None => {
            let mut sigs = load_bundled_signatures();
            if let Some(home) = home_dir() {
                let user_dir = home.join(".spectral").join("signatures");
                sigs.extend(load_signatures_from_dir(&user_dir));
            }
            sigs
        }
    }
}

fn home_dir() -> Option<PathBuf> {
    std::env::var("HOME").ok().map(PathBuf::from)
        .or_else(|| std::env::var("USERPROFILE").ok().map(PathBuf::from))
}

// ─── Matching ─────────────────────────────────────────────────────────────────

const MAX_FILE_BYTES: u64 = 16 * 1024 * 1024;

fn indicator_matches_content(indicator: &Indicator, content: &str) -> bool {
    match indicator.kind {
        IndicatorType::Regex => {
            Regex::new(&indicator.pattern)
                .map(|re| re.is_match(content))
                .unwrap_or(false)
        }
        IndicatorType::String => content.contains(&indicator.pattern),
        IndicatorType::FilePath => false,
    }
}

fn indicator_matches_path(indicator: &Indicator, path_str: &str) -> bool {
    if indicator.kind != IndicatorType::FilePath {
        return false;
    }
    if indicator.pattern.contains('*') {
        let parts: Vec<&str> = indicator.pattern.split('*').filter(|s| !s.is_empty()).collect();
        let mut remaining = path_str;
        for part in parts {
            match remaining.find(part) {
                Some(idx) => remaining = &remaining[idx + part.len()..],
                None => return false,
            }
        }
        true
    } else {
        path_str.contains(&indicator.pattern)
    }
}

// Return the 1-indexed line number and trimmed line text for the first match.
fn find_indicator_line(indicator: &Indicator, content: &str) -> Option<(usize, String)> {
    match indicator.kind {
        IndicatorType::Regex => {
            let re = Regex::new(&indicator.pattern).ok()?;
            for (idx, line) in content.lines().enumerate() {
                if re.is_match(line) {
                    return Some((idx + 1, line.trim().to_string()));
                }
            }
            None
        }
        IndicatorType::String => {
            for (idx, line) in content.lines().enumerate() {
                if line.contains(&indicator.pattern) {
                    return Some((idx + 1, line.trim().to_string()));
                }
            }
            None
        }
        IndicatorType::FilePath => None,
    }
}

fn apply_signature_to_content(sig: &Signature, content: &str, file: &str) -> Option<Finding> {
    let content_indicators: Vec<&Indicator> = sig.indicators.iter()
        .filter(|i| i.kind != IndicatorType::FilePath)
        .collect();

    if content_indicators.is_empty() {
        return None;
    }

    let matched: Vec<String> = content_indicators.iter()
        .filter(|i| indicator_matches_content(i, content))
        .map(|i| i.pattern.clone())
        .collect();

    if matched.is_empty() {
        return None;
    }

    if sig.match_all && matched.len() < content_indicators.len() {
        return None;
    }

    let (line, context) = content_indicators.iter()
        .filter(|i| indicator_matches_content(i, content))
        .find_map(|i| find_indicator_line(i, content))
        .map(|(ln, ctx)| (Some(ln), Some(ctx)))
        .unwrap_or((None, None));

    Some(Finding {
        id: sig.id.clone(),
        name: sig.name.clone(),
        category: sig.category.clone(),
        model_family: sig.model_family.clone(),
        confidence: sig.confidence.clone(),
        description: sig.description.clone(),
        technique: sig.technique.clone(),
        indicators_matched: matched,
        file: file.to_string(),
        line,
        context,
    })
}

fn apply_signature_to_path(sig: &Signature, path_str: &str) -> Option<Finding> {
    let path_indicators: Vec<&Indicator> = sig.indicators.iter()
        .filter(|i| i.kind == IndicatorType::FilePath)
        .collect();

    if path_indicators.is_empty() {
        return None;
    }

    let matched: Vec<String> = path_indicators.iter()
        .filter(|i| indicator_matches_path(i, path_str))
        .map(|i| i.pattern.clone())
        .collect();

    if matched.is_empty() {
        return None;
    }

    Some(Finding {
        id: sig.id.clone(),
        name: sig.name.clone(),
        category: sig.category.clone(),
        model_family: sig.model_family.clone(),
        confidence: sig.confidence.clone(),
        description: sig.description.clone(),
        technique: sig.technique.clone(),
        indicators_matched: matched,
        file: path_str.to_string(),
        line: None,
        context: Some("filesystem artifact".to_string()),
    })
}

fn scan_path(path: &Path, sigs: &[Signature]) -> Vec<Finding> {
    let mut findings = Vec::new();
    let path_str = path.to_string_lossy();

    for sig in sigs {
        if let Some(f) = apply_signature_to_path(sig, &path_str) {
            findings.push(f);
        }
    }

    if path.is_file() {
        let size_bytes = path.metadata().map(|m| m.len()).unwrap_or(0);
        if size_bytes == 0 || size_bytes > MAX_FILE_BYTES {
            return findings;
        }
        if let Ok(content) = fs::read_to_string(path) {
            findings.extend(scan_text(&content, &path_str, sigs));
        }
    }

    findings
}

fn scan_text(content: &str, label: &str, sigs: &[Signature]) -> Vec<Finding> {
    sigs.iter()
        .filter(|s| s.indicators.iter().any(|i| i.kind != IndicatorType::FilePath))
        .filter_map(|sig| apply_signature_to_content(sig, content, label))
        .collect()
}

// ─── Confidence helpers ───────────────────────────────────────────────────────

fn confidence_rank(c: &str) -> u8 {
    match c { "high" => 2, "medium" => 1, _ => 0 }
}

fn confidence_label(c: &str) -> &str {
    match c {
        "high"   => "HIGH  ",
        "medium" => "MED   ",
        "low"    => "LOW   ",
        other    => other,
    }
}

// ─── CLI ─────────────────────────────────────────────────────────────────────

#[derive(Parser)]
#[command(
    name    = "spectral",
    version = "0.7.0",
    about   = "AI artifact scanner -- detects indicators of AI/LLM activity in files, code, logs, and filesystems"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,

    #[arg(long, global = true)]
    sigs: Option<PathBuf>,

    #[arg(long, global = true)]
    json: bool,

    #[arg(short, long, global = true)]
    quiet: bool,
}

#[derive(Subcommand)]
enum Command {
    /// Scan a file, directory, or log for AI artifacts
    Scan {
        target: PathBuf,
        #[arg(short, long)]
        category: Option<String>,
        #[arg(long, default_value_t = true)]
        skip_git: bool,
        #[arg(long, default_value_t = false)]
        skip_tests: bool,
        #[arg(long)]
        min_confidence: Option<String>,
    },
    /// Scan environment variables or a .env file for AI keys and config
    Env {
        /// .env file to scan (default: reads stdin -- pipe from printenv or cat .env)
        #[arg(long)]
        file: Option<PathBuf>,
        #[arg(short, long)]
        category: Option<String>,
        #[arg(long)]
        min_confidence: Option<String>,
    },
    /// List all loaded signatures
    List {
        #[arg(short, long)]
        category: Option<String>,
    },
    /// Validate signature files for common issues
    Check {
        /// Signature file or directory to validate (default: bundled + ~/.spectral/signatures/)
        target: Option<PathBuf>,
    },
    /// Scan git commit history for AI attribution artifacts
    Git {
        repo: Option<PathBuf>,
        #[arg(long)]
        since: Option<String>,
        #[arg(long)]
        json: bool,
    },
}

// ─── Output helpers ───────────────────────────────────────────────────────────

fn print_finding(f: &Finding) {
    println!("[{}] {} ({})", confidence_label(&f.confidence), f.name, f.id);
    println!("  model:     {}", f.model_family);
    println!("  category:  {}", f.category);
    println!("  technique: {}", f.technique);
    match f.line {
        Some(ln) => println!("  file:      {}:{}", f.file, ln),
        None      => println!("  file:      {}", f.file),
    }
    println!("  matched:   {}", f.indicators_matched.join(" | "));
    if let Some(ctx) = &f.context {
        println!("  context:   {}", ctx);
    }
    println!();
}

fn sort_findings(findings: &mut Vec<Finding>) {
    findings.sort_by(|a, b| {
        confidence_rank(&b.confidence).cmp(&confidence_rank(&a.confidence))
            .then(a.id.cmp(&b.id))
    });
}

// ─── Git history scan ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
struct CommitHit {
    hash: String,
    date: String,
    author: String,
    subject: String,
    matched: Vec<String>,
}

#[derive(Debug, Serialize)]
struct GitScanResult {
    repo: String,
    commits_scanned: usize,
    ai_commits: usize,
    first_hit: Option<CommitHit>,
    last_hit: Option<CommitHit>,
    hits: Vec<CommitHit>,
}

struct CommitPattern {
    name: &'static str,
    pattern: &'static str,
}

const COMMIT_PATTERNS: &[CommitPattern] = &[
    CommitPattern { name: "claude-coauthor",       pattern: r"Co-Authored-By:\s*Claude" },
    CommitPattern { name: "claude-pr-footer",      pattern: r"Generated with \[Claude Code\]" },
    CommitPattern { name: "claude-noreply",        pattern: r"noreply@anthropic\.com" },
    CommitPattern { name: "copilot-coauthor",      pattern: r"Co-Authored-By:.*github-actions\[bot\]" },
    CommitPattern { name: "copilot-workspace",     pattern: r"Copilot Workspace" },
    CommitPattern { name: "gpt-coauthor",          pattern: r"Co-Authored-By:.*openai" },
    CommitPattern { name: "cursor-agent",          pattern: r"(?i)(generated|written|created) (by|with|using) cursor" },
    CommitPattern { name: "devin-agent",           pattern: r"Devin AI|app\.devin\.ai" },
    CommitPattern { name: "codeium-author",        pattern: r"(?i)codeium" },
    CommitPattern { name: "aider-coauthor",        pattern: r"(?i)Co-[Aa]uthored-[Bb]y:\s*aider" },
    CommitPattern { name: "aider-footer",          pattern: r"aider v\d+\.\d+\.\d+" },
    CommitPattern { name: "amazon-q-coauthor",     pattern: r"(?i)(Co-Authored-By:.*amazon.q|generated (with|by) amazon q|CodeWhisperer)" },
    CommitPattern { name: "gemini-coauthor",       pattern: r"(?i)(Co-Authored-By:.*gemini|generated (with|by) (gemini|duet.ai))" },
    CommitPattern { name: "tabnine-coauthor",      pattern: r"(?i)Co-Authored-By:.*tabnine" },
    CommitPattern { name: "cody-coauthor",         pattern: r"(?i)(Co-Authored-By:.*cody|generated (with|by) (sourcegraph |cody))" },
    CommitPattern { name: "jetbrains-ai",          pattern: r"(?i)JetBrains AI" },
    CommitPattern { name: "swe-agent",             pattern: r"(?i)swe.?agent" },
    CommitPattern { name: "ai-pr-marker",          pattern: r"\[AI\]|\[LLM\]|\[GPT\]|\[Claude\]|\[Copilot\]" },
];

fn scan_git_history(repo: &Path, since: Option<&str>, quiet: bool) -> Result<GitScanResult> {
    use std::process::Command;

    let repo_str = repo.to_string_lossy().to_string();

    let matchers: Vec<(Regex, &str)> = COMMIT_PATTERNS.iter()
        .filter_map(|p| Regex::new(p.pattern).ok().map(|re| (re, p.name)))
        .collect();

    const SENTINEL: &str = "---SPECTRAL-SEP---";
    let fmt = format!("SPEC|%H|%ai|%ae|%s%n%B{}", SENTINEL);
    let fmt_arg = format!("--format={}", fmt);

    let mut args = vec!["-C", &repo_str, "log", "--all", &fmt_arg];
    let since_arg;
    if let Some(s) = since {
        since_arg = format!("--since={}", s);
        args.push(&since_arg);
    }

    let output = Command::new("git").args(&args).output()?;

    if !output.status.success() {
        anyhow::bail!("git log failed: {}", String::from_utf8_lossy(&output.stderr));
    }

    let raw = String::from_utf8_lossy(&output.stdout);
    let commits = parse_git_log(&raw);

    if !quiet {
        eprintln!("spectral: scanning {} commits in {}", commits.len(), repo_str);
    }

    let mut hits: Vec<CommitHit> = commits.iter()
        .filter_map(|(hash, date, author, subject, body)| {
            match_commit(hash, date, author, subject, body, &matchers)
        })
        .collect();

    let total = commits.len();
    let ai_commits = hits.len();
    hits.reverse(); // git log is newest-first; reverse for chronological order
    let first_hit = hits.first().cloned();
    let last_hit  = hits.last().cloned();

    Ok(GitScanResult { repo: repo_str, commits_scanned: total, ai_commits, first_hit, last_hit, hits })
}

fn parse_git_log(raw: &str) -> Vec<(String, String, String, String, String)> {
    const SENTINEL: &str = "---SPECTRAL-SEP---";
    let mut commits = Vec::new();

    for block in raw.split(SENTINEL) {
        let block = block.trim();
        if block.is_empty() { continue; }

        let mut lines = block.lines();
        let header = match lines.next() {
            Some(h) if h.starts_with("SPEC|") => h,
            _ => continue,
        };

        let mut parts = header.splitn(5, '|');
        parts.next(); // "SPEC" prefix
        let hash    = parts.next().unwrap_or("").to_string();
        let date    = parts.next().unwrap_or("").to_string();
        let author  = parts.next().unwrap_or("").to_string();
        let subject = parts.next().unwrap_or("").to_string();
        let body    = lines.collect::<Vec<_>>().join("\n");

        if hash.is_empty() { continue; }
        commits.push((hash, date, author, subject, body));
    }

    commits
}

fn match_commit(
    hash: &str, date: &str, author: &str, subject: &str, body: &str,
    matchers: &[(Regex, &str)],
) -> Option<CommitHit> {
    let full_text = format!("{}\n{}", subject, body);
    let matched: Vec<String> = matchers.iter()
        .filter(|(re, _)| re.is_match(&full_text))
        .map(|(_, name)| name.to_string())
        .collect();

    if matched.is_empty() {
        return None;
    }

    Some(CommitHit {
        hash: hash.to_string(),
        date: date.get(..10).unwrap_or(date).to_string(),
        author: author.to_string(),
        subject: subject.to_string(),
        matched,
    })
}

// ─── Signature validation ────────────────────────────────────────────────────

#[derive(Debug)]
struct ValidationIssue {
    sig_id: String,
    severity: &'static str,
    message: String,
}

const VALID_CONFIDENCE: &[&str] = &["high", "medium", "low"];
const VALID_PREFIXES: &[&str] = &["code/", "agentic/", "infrastructure/", "content/", "security/"];

fn validate_signatures(sigs: &[Signature], source: &str) -> Vec<ValidationIssue> {
    let mut issues = Vec::new();
    let mut seen_ids = std::collections::HashSet::new();

    for sig in sigs {
        if !seen_ids.insert(sig.id.clone()) {
            issues.push(ValidationIssue {
                sig_id: sig.id.clone(),
                severity: "ERROR",
                message: format!("duplicate ID '{}' ({})", sig.id, source),
            });
        }

        if !VALID_CONFIDENCE.contains(&sig.confidence.as_str()) {
            issues.push(ValidationIssue {
                sig_id: sig.id.clone(),
                severity: "ERROR",
                message: format!("invalid confidence '{}' -- must be high/medium/low", sig.confidence),
            });
        }

        if !VALID_PREFIXES.iter().any(|p| sig.category.starts_with(p)) {
            issues.push(ValidationIssue {
                sig_id: sig.id.clone(),
                severity: "WARN",
                message: format!("category '{}' does not start with a known prefix (code|agentic|infrastructure|content)", sig.category),
            });
        }

        if sig.indicators.is_empty() {
            issues.push(ValidationIssue {
                sig_id: sig.id.clone(),
                severity: "ERROR",
                message: "no indicators defined".to_string(),
            });
        }

        for ind in &sig.indicators {
            match ind.kind {
                IndicatorType::String => {
                    if ind.pattern.len() < 6 {
                        issues.push(ValidationIssue {
                            sig_id: sig.id.clone(),
                            severity: "WARN",
                            message: format!(
                                "string indicator '{}' is {} chars -- short strings collide with base64. Use regex with word-boundary anchors instead.",
                                ind.pattern, ind.pattern.len()
                            ),
                        });
                    }
                }
                IndicatorType::Regex => {
                    if let Err(e) = Regex::new(&ind.pattern) {
                        issues.push(ValidationIssue {
                            sig_id: sig.id.clone(),
                            severity: "ERROR",
                            message: format!("invalid regex '{}': {}", ind.pattern, e),
                        });
                    }
                }
                IndicatorType::FilePath => {}
            }
        }
    }

    issues
}

// ─── Commands ─────────────────────────────────────────────────────────────────

fn cmd_scan(
    target: PathBuf,
    category: Option<String>,
    skip_git: bool,
    skip_tests: bool,
    min_confidence: Option<String>,
    all_sigs: Vec<Signature>,
    json: bool,
    quiet: bool,
) -> Result<()> {
    if !target.exists() {
        anyhow::bail!("target not found: {}", target.display());
    }

    let sigs: Vec<Signature> = all_sigs.into_iter()
        .filter(|s| category.as_ref().map_or(true, |c| s.category.starts_with(c)))
        .collect();

    const SKIP_TEST_DIRS: &[&str] = &[
        "test", "tests", "__tests__", "spec", "specs",
        "fixtures", "cassettes", "vcr_cassettes",
        "recordings", "snapshots", "__snapshots__",
        "testdata", "test_data",
    ];

    let entries: Vec<_> = WalkDir::new(&target)
        .into_iter()
        .filter_entry(|e| {
            if skip_git && e.file_name() == ".git" {
                return false;
            }
            if skip_tests && e.file_type().is_dir() {
                let name = e.file_name().to_string_lossy();
                if SKIP_TEST_DIRS.iter().any(|&d| name.eq_ignore_ascii_case(d)) {
                    return false;
                }
            }
            true
        })
        .filter_map(|e| e.ok())
        .collect();

    let findings_per_entry: Vec<Vec<Finding>> = entries.par_iter()
        .map(|entry| scan_path(entry.path(), &sigs))
        .collect();

    let mut seen: std::collections::HashSet<(String, String)> = std::collections::HashSet::new();
    let mut findings: Vec<Finding> = Vec::new();

    for chunk in findings_per_entry {
        for f in chunk {
            if seen.insert((f.id.clone(), f.file.clone())) {
                findings.push(f);
            }
        }
    }

    let min_rank = min_confidence.as_deref().map(confidence_rank).unwrap_or(0);
    findings.retain(|f| confidence_rank(&f.confidence) >= min_rank);
    sort_findings(&mut findings);

    let result = ScanResult {
        target: target.to_string_lossy().to_string(),
        signatures_loaded: sigs.len(),
        findings_count: findings.len(),
        findings,
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&result)?);
    } else if result.findings.is_empty() {
        if !quiet {
            println!("spectral: no AI artifacts detected in {}", result.target);
        }
    } else {
        if !quiet {
            println!("spectral: {} finding(s) in {}\n", result.findings_count, result.target);
        }
        for f in &result.findings {
            print_finding(f);
        }
    }

    Ok(())
}

fn cmd_env(
    file: Option<PathBuf>,
    category: Option<String>,
    min_confidence: Option<String>,
    all_sigs: Vec<Signature>,
    json: bool,
    quiet: bool,
) -> Result<()> {
    let content = match file {
        Some(ref path) => fs::read_to_string(path)
            .map_err(|e| anyhow::anyhow!("cannot read {}: {}", path.display(), e))?,
        None => {
            let mut buf = String::new();
            std::io::stdin().read_to_string(&mut buf)
                .map_err(|e| anyhow::anyhow!("stdin read failed: {}", e))?;
            buf
        }
    };

    let label = file.as_ref()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|| "<stdin>".to_string());

    let sigs: Vec<Signature> = all_sigs.into_iter()
        .filter(|s| category.as_ref().map_or(true, |c| s.category.starts_with(c)))
        .collect();

    let mut findings = scan_text(&content, &label, &sigs);

    let min_rank = min_confidence.as_deref().map(confidence_rank).unwrap_or(0);
    findings.retain(|f| confidence_rank(&f.confidence) >= min_rank);
    sort_findings(&mut findings);

    if json {
        let result = ScanResult {
            target: label,
            signatures_loaded: sigs.len(),
            findings_count: findings.len(),
            findings,
        };
        println!("{}", serde_json::to_string_pretty(&result)?);
    } else if findings.is_empty() {
        if !quiet {
            println!("spectral: no AI artifacts detected in {}", label);
        }
    } else {
        if !quiet {
            println!("spectral: {} finding(s) in {}\n", findings.len(), label);
        }
        for f in &findings {
            print_finding(f);
        }
    }

    Ok(())
}

fn cmd_git(repo: Option<PathBuf>, since: Option<String>, json: bool, quiet: bool) -> Result<()> {
    let repo_path = repo.unwrap_or_else(|| PathBuf::from("."));
    if !repo_path.exists() {
        anyhow::bail!("path not found: {}", repo_path.display());
    }
    let result = scan_git_history(&repo_path, since.as_deref(), quiet)?;

    if json {
        println!("{}", serde_json::to_string_pretty(&result)?);
        return Ok(());
    }

    println!("repo:             {}", result.repo);
    println!("commits scanned:  {}", result.commits_scanned);
    println!("AI commits:       {} ({:.1}%)",
        result.ai_commits,
        if result.commits_scanned > 0 {
            result.ai_commits as f64 / result.commits_scanned as f64 * 100.0
        } else { 0.0 });

    if let Some(ref first) = result.first_hit {
        println!("first AI commit:  {} {} [{}]  {}",
            first.date, &first.hash[..8], first.matched.join(", "), first.subject);
    }
    if result.ai_commits > 1 {
        if let Some(ref last) = result.last_hit {
            println!("last AI commit:   {} {} [{}]  {}",
                last.date, &last.hash[..8], last.matched.join(", "), last.subject);
        }
    }

    if !result.hits.is_empty() && !quiet {
        println!("\n--- All AI-attributed commits ---");
        for h in &result.hits {
            println!("  {} {}  [{}]  {}", h.date, &h.hash[..8], h.matched.join(", "), h.subject);
        }
    }

    if result.ai_commits == 0 {
        println!("no AI-attributed commits found");
    }

    Ok(())
}

fn cmd_check(target: Option<PathBuf>, all_sigs: Vec<Signature>) -> Result<()> {
    let (sigs_to_check, source_label) = match target {
        Some(ref path) => {
            let sigs = if path.is_file() {
                let content = fs::read_to_string(path)?;
                let mut v = Vec::new();
                for doc in content.split("\n---\n") {
                    let doc = doc.trim();
                    if doc.is_empty() { continue; }
                    match serde_yaml::from_str::<Signature>(doc) {
                        Ok(s) => v.push(s),
                        Err(e) => eprintln!("spectral: parse error: {}: {}", path.display(), e),
                    }
                }
                v
            } else {
                load_signatures_from_dir(path)
            };
            (sigs, path.to_string_lossy().to_string())
        }
        None => (all_sigs, "bundled + user overlay".to_string()),
    };

    let issues = validate_signatures(&sigs_to_check, &source_label);

    if issues.is_empty() {
        println!("spectral check: {} signature(s) -- OK", sigs_to_check.len());
    } else {
        let errors = issues.iter().filter(|i| i.severity == "ERROR").count();
        let warns  = issues.iter().filter(|i| i.severity == "WARN").count();
        for issue in &issues {
            println!("[{}] {} -- {}", issue.severity, issue.sig_id, issue.message);
        }
        println!("\n{} signature(s) checked -- {} error(s), {} warning(s)",
            sigs_to_check.len(), errors, warns);
        if errors > 0 {
            std::process::exit(1);
        }
    }

    Ok(())
}

fn cmd_list(category: Option<String>, sigs: Vec<Signature>, quiet: bool) {
    let filtered: Vec<&Signature> = sigs.iter()
        .filter(|s| category.as_ref().map_or(true, |c| s.category.starts_with(c)))
        .collect();
    println!("{:<12} {:<40} {:<8} {}", "ID", "NAME", "CONF", "MODEL");
    println!("{}", "-".repeat(80));
    for sig in &filtered {
        println!("{:<12} {:<40} {:<8} {}", sig.id, sig.name, sig.confidence, sig.model_family);
    }
    if !quiet {
        eprintln!("\n{} signature(s) loaded", filtered.len());
    }
}

// ─── Main ─────────────────────────────────────────────────────────────────────

fn main() -> Result<()> {
    let cli = Cli::parse();
    let sigs = load_signatures(cli.sigs.as_deref());

    match cli.command {
        Command::Scan { target, category, skip_git, skip_tests, min_confidence } =>
            cmd_scan(target, category, skip_git, skip_tests, min_confidence, sigs, cli.json, cli.quiet),

        Command::Env { file, category, min_confidence } =>
            cmd_env(file, category, min_confidence, sigs, cli.json, cli.quiet),

        Command::Git { repo, since, json } =>
            cmd_git(repo, since, json, cli.quiet),

        Command::Check { target } =>
            cmd_check(target, sigs),

        Command::List { category } => {
            cmd_list(category, sigs, cli.quiet);
            Ok(())
        }
    }
}
