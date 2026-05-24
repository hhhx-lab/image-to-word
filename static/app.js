const form = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#fileInput");
const fileName = document.querySelector("#fileName");
const dropzone = document.querySelector("#dropzone");
const submitBtn = document.querySelector("#submitBtn");
const jobLog = document.querySelector("#jobLog");
const preview = document.querySelector("#preview");
const configStatus = document.querySelector("#configStatus");
const downloadDocx = document.querySelector("#downloadDocx");
const downloadMd = document.querySelector("#downloadMd");
const tabs = [...document.querySelectorAll(".tab")];

let currentJob = null;
let previewMode = "html";
let pollTimer = null;

function log(message, tone = "") {
  jobLog.innerHTML = `<div class="log-row ${tone}">${escapeHtml(message)}</div>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setDownload(anchor, url) {
  if (url) {
    anchor.href = url;
    anchor.classList.remove("disabled");
  } else {
    anchor.href = "#";
    anchor.classList.add("disabled");
  }
}

function renderPreview(job) {
  setDownload(downloadDocx, job.downloads?.docx);
  setDownload(downloadMd, job.downloads?.markdown);

  if (job.status !== "done") {
    preview.innerHTML = `<div class="empty-state">${escapeHtml(job.message || "处理中")}</div>`;
    return;
  }

  if (previewMode === "html" && job.downloads?.html) {
    preview.innerHTML = `<iframe title="HTML preview" src="${job.downloads.html}"></iframe>`;
    return;
  }

  const markdown = job.markdown || "没有可预览的 Markdown 内容";
  const suffix = job.preview_truncated ? "\n\n[预览已截断，完整内容请下载 Markdown]" : "";
  preview.innerHTML = `<pre class="markdown-view">${escapeHtml(markdown + suffix)}</pre>`;
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    configStatus.textContent = health.mineru_configured ? "MinerU 已配置" : "缺少 MinerU Key";
    configStatus.className = `status-pill ${health.mineru_configured ? "ok" : "bad"}`;
  } catch {
    configStatus.textContent = "服务未就绪";
    configStatus.className = "status-pill bad";
  }
}

async function pollJob(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);
  const job = await response.json();
  currentJob = job;
  log(job.message || job.status, job.status === "failed" ? "muted" : "");
  renderPreview(job);

  if (job.status === "done" || job.status === "failed") {
    submitBtn.disabled = false;
    submitBtn.textContent = "开始转换";
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files[0]?.name || "选择文件";
});

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
  });
});

dropzone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (!file) return;
  fileInput.files = event.dataTransfer.files;
  fileName.textContent = file.name;
});

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    previewMode = tab.dataset.mode;
    tabs.forEach((item) => item.classList.toggle("active", item === tab));
    if (currentJob) renderPreview(currentJob);
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files[0]) {
    log("请选择文件", "muted");
    return;
  }

  const data = new FormData(form);
  submitBtn.disabled = true;
  submitBtn.textContent = "提交中";
  log("正在上传");
  preview.innerHTML = `<div class="empty-state">提交中</div>`;

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: data,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    const job = await response.json();
    currentJob = job;
    log(job.message || "已提交");
    submitBtn.textContent = "转换中";
    await pollJob(job.id);
    pollTimer = setInterval(() => pollJob(job.id), 5000);
  } catch (error) {
    submitBtn.disabled = false;
    submitBtn.textContent = "开始转换";
    log(error.message || "提交失败", "muted");
    preview.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "提交失败")}</div>`;
  }
});

checkHealth();
