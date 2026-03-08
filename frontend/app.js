function formatNumber(value) {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed.toLocaleString() : String(value || "");
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) {
    node.textContent = value || "-";
  }
}

const THEME_STORAGE_KEY = "health-agent-theme";
const THEME_LIGHT = "light";
const THEME_DARK = "dark";

function storedTheme() {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return value === THEME_DARK || value === THEME_LIGHT ? value : "";
  } catch (error) {
    return "";
  }
}

function preferredTheme() {
  const stored = storedTheme();
  if (stored) {
    return stored;
  }
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? THEME_DARK
    : THEME_LIGHT;
}

function updateThemeToggle(theme) {
  const toggle = document.getElementById("theme-toggle");
  if (!toggle) {
    return;
  }
  const isDark = theme === THEME_DARK;
  const label = toggle.querySelector(".theme-toggle-label");
  const autoEnabled = !storedTheme();
  const nextModeLabel = isDark ? "light" : "dark";
  toggle.dataset.theme = theme;
  toggle.dataset.mode = autoEnabled ? "auto" : "manual";
  toggle.setAttribute("aria-pressed", String(isDark));
  toggle.setAttribute("aria-label", `Switch to ${nextModeLabel} mode`);
  toggle.setAttribute("title", `Switch to ${nextModeLabel} mode`);
  // if (label) {
  //   label.textContent = autoEnabled
  //     ? `Auto · ${isDark ? "" : ""}`
  //     : `${isDark ? "" : ""}`;
  // }
}

function applyTheme(theme, persist = true) {
  const resolved = theme === THEME_DARK ? THEME_DARK : THEME_LIGHT;
  document.documentElement.dataset.theme = resolved;
  updateThemeToggle(resolved);
  if (persist) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, resolved);
    } catch (error) {
      // Ignore storage issues and keep the theme applied for the current session.
    }
  }
}

function initThemeToggle() {
  const toggle = document.getElementById("theme-toggle");
  applyTheme(preferredTheme(), false);
  const mediaQuery = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const handleSystemThemeChange = (event) => {
    if (!storedTheme()) {
      applyTheme(event.matches ? THEME_DARK : THEME_LIGHT, false);
    }
  };
  if (mediaQuery) {
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handleSystemThemeChange);
    } else if (typeof mediaQuery.addListener === "function") {
      mediaQuery.addListener(handleSystemThemeChange);
    }
  }
  if (!toggle) {
    return;
  }
  toggle.addEventListener("click", () => {
    const nextTheme = document.documentElement.dataset.theme === THEME_DARK ? THEME_LIGHT : THEME_DARK;
    applyTheme(nextTheme);
  });
}

function resolvePreviewImageUrl(blog) {
  if (blog?.image_url) {
    return blog.image_url;
  }
  const candidate = String(blog?.file_url || "").trim();
  if (!candidate) {
    return "";
  }
  if (/\.(png|jpe?g|gif|webp|avif|svg)(\?.*)?$/i.test(candidate)) {
    return candidate;
  }
  return "";
}

function statusBadge(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "success") {
    return "success";
  }
  if (normalized === "error") {
    return "error";
  }
  return "other";
}

function createEmptyState() {
  const template = document.getElementById("empty-state-template");
  return template ? template.content.cloneNode(true) : document.createTextNode("No data available.");
}

function containsHtmlMarkup(text) {
  return /<\/?[a-z][^>]*>/i.test(text || "");
}

function renderInlineMarkdown(text) {
  let rendered = escapeHtml(text || "");
  rendered = rendered.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  rendered = rendered.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  rendered = rendered.replace(/\*(.+?)\*/g, "<em>$1</em>");
  rendered = rendered.replace(/`([^`]+)`/g, "<code>$1</code>");
  return rendered;
}

function markdownToHtml(text) {
  const input = String(text || "").replace(/\r\n/g, "\n").trim();
  if (!input) {
    return "";
  }
  if (containsHtmlMarkup(input)) {
    return input;
  }

  const blocks = [];
  let paragraph = [];
  let unordered = [];
  let ordered = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push(`<p>${paragraph.map((line) => renderInlineMarkdown(line)).join(" ")}</p>`);
      paragraph = [];
    }
  };

  const flushUnordered = () => {
    if (unordered.length) {
      blocks.push(`<ul>${unordered.map((item) => `<li>${item}</li>`).join("")}</ul>`);
      unordered = [];
    }
  };

  const flushOrdered = () => {
    if (ordered.length) {
      blocks.push(`<ol>${ordered.map((item) => `<li>${item}</li>`).join("")}</ol>`);
      ordered = [];
    }
  };

  input.split("\n").forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushUnordered();
      flushOrdered();
      return;
    }
    if (/^(---|\*\*\*|___)$/.test(line)) {
      flushParagraph();
      flushUnordered();
      flushOrdered();
      blocks.push("<hr>");
      return;
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushParagraph();
      flushUnordered();
      flushOrdered();
      const level = heading[1].length;
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      return;
    }
    const unorderedMatch = line.match(/^[-*]\s+(.*)$/);
    if (unorderedMatch) {
      flushParagraph();
      flushOrdered();
      unordered.push(renderInlineMarkdown(unorderedMatch[1]));
      return;
    }
    const orderedMatch = line.match(/^\d+\.\s+(.*)$/);
    if (orderedMatch) {
      flushParagraph();
      flushUnordered();
      ordered.push(renderInlineMarkdown(orderedMatch[1]));
      return;
    }
    flushUnordered();
    flushOrdered();
    paragraph.push(line);
  });

  flushParagraph();
  flushUnordered();
  flushOrdered();
  return blocks.join("");
}

function renderArticleContent(text) {
  const rendered = markdownToHtml(text);
  return rendered || `<div class="empty-state">No content available.</div>`;
}

function renderMetricCards(stats) {
  const cards = [
    ["Total events", stats.total_events, "◌", "teal"],
    ["Runs", stats.total_runs, "▶", "indigo"],
    ["Errors", stats.error_events, "⚠", "rose"],
    ["Success events", stats.success_events, "✓", "emerald"],
    ["Memory facts", stats.memory_facts, "✦", "amber"],
    ["Requests", stats.request_count, "↗", "cyan"],
    ["Prompt tokens", stats.prompt_tokens, "⌘", "violet"],
    ["Completion tokens", stats.completion_tokens, "✎", "sky"],
    ["Total tokens", stats.total_tokens, "◎", "blue"],
  ];
  const grid = document.getElementById("metric-cards");
  if (!grid) {
    return;
  }
  grid.innerHTML = cards.map(([label, value, icon, tone]) => `
    <article class="metric-card metric-card-${tone}">
      <div class="metric-card-head">
        <span class="label">${label}</span>
        <span class="metric-icon" aria-hidden="true">${icon}</span>
      </div>
      <strong>${formatNumber(value)}</strong>
    </article>
  `).join("");
}

function dashboardChartSeries() {
  return [
    { key: "total", label: "Total events", color: "var(--chart-total)" },
    { key: "success", label: "Success", color: "var(--chart-success)" },
    { key: "error", label: "Error", color: "var(--chart-error)" },
  ];
}

function tokenChartSeries() {
  return [
    { key: "request_count", label: "Requests", color: "var(--chart-request)" },
    { key: "total_tokens", label: "Total tokens", color: "var(--chart-token)" },
  ];
}

function renderBarChart(containerId, data, series) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  if (!Array.isArray(data) || data.length === 0) {
    container.innerHTML = "";
    container.appendChild(createEmptyState());
    return;
  }
  const maxValue = Math.max(
    ...data.flatMap((entry) => series.map((item) => Number(entry[item.key] || 0))),
    1
  );
  container.innerHTML = data.map((entry) => {
    const bars = series.map((item) => {
      const value = Number(entry[item.key] || 0);
      const height = Math.max(4, Math.round((value / maxValue) * 190));
      return `<div class="bar" style="height:${height}px;background:${item.color}" title="${item.label}: ${formatNumber(value)}"></div>`;
    }).join("");
    return `
      <div class="bar-group">
        <div class="bar-stack">${bars}</div>
        <div class="bar-label">${entry.label}</div>
      </div>
    `;
  }).join("");
}

function renderRuns(runs) {
  const body = document.getElementById("runs-body");
  if (!body) {
    return;
  }
  if (!Array.isArray(runs) || runs.length === 0) {
    body.innerHTML = `<tr><td colspan="7"><div class="empty-state">No runs found.</div></td></tr>`;
    return;
  }
  body.innerHTML = runs.map((run) => `
    <tr>
      <td>${run.run_id}</td>
      <td>${formatNumber(run.event_count)}</td>
      <td>${formatNumber(run.success_count)}</td>
      <td>${formatNumber(run.error_count)}</td>
      <td>${formatNumber(run.request_count)}</td>
      <td>${formatNumber(run.total_tokens)}</td>
      <td>${run.last_seen || "-"}</td>
    </tr>
  `).join("");
}

function renderLogs(logs) {
  const body = document.getElementById("logs-body");
  if (!body) {
    return;
  }
  if (!Array.isArray(logs) || logs.length === 0) {
    body.innerHTML = `<tr><td colspan="7"><div class="empty-state">No logs found.</div></td></tr>`;
    return;
  }
  body.innerHTML = logs.map((log) => `
    <tr>
      <td>${formatNumber(log.id)}</td>
      <td>${log.created_at || "-"}</td>
      <td>${log.run_id || "-"}</td>
      <td>${log.step || "-"}</td>
      <td><span class="status-badge ${statusBadge(log.status)}">${log.status || "-"}</span></td>
      <td>${log.item_slug || "-"}</td>
      <td>${log.message || "-"}</td>
    </tr>
  `).join("");
}

function renderMemory(memory) {
  const list = document.getElementById("memory-list");
  if (!list) {
    return;
  }
  if (!Array.isArray(memory) || memory.length === 0) {
    list.innerHTML = "";
    list.appendChild(createEmptyState());
    return;
  }
  list.innerHTML = memory.map((item) => `
    <article class="memory-card">
      <div class="memory-meta">
        <span>${item.category_name || "Uncategorized"}</span>
        <span>${item.confidence || "confidence n/a"}</span>
        <span>${item.created_at || "-"}</span>
      </div>
      <strong>${item.memory_key || "Fact"}</strong>
      <p>${item.verified_fact || "-"}</p>
    </article>
  `).join("");
}

function renderBlogs(blogs) {
  const grid = document.getElementById("blog-grid");
  if (!grid) {
    return;
  }
  if (!Array.isArray(blogs) || blogs.length === 0) {
    grid.innerHTML = "";
    grid.appendChild(createEmptyState());
    return;
  }
  grid.innerHTML = blogs.map((blog) => {
    const previewImageUrl = resolvePreviewImageUrl(blog);
    const media = previewImageUrl
      ? `<div class="blog-media"><img src="${previewImageUrl}" alt="${blog.title || "Blog image"}"></div>`
      : `<div class="blog-media"><div class="empty-state media-empty-state">No image available.</div></div>`;
    const detailHref = blog.slug
      ? `/frontend/blog-detail.html?slug=${encodeURIComponent(blog.slug)}`
      : "#";
    return `
      <article class="blog-card">
        ${media}
        <div class="blog-body">
          <div class="chip-row">
            <span class="chip">${blog.category_name || "Uncategorized"}</span>
            <span class="chip">${blog.created_at || "-"}</span>
          </div>
          <h2>${blog.title || "Untitled blog"}</h2>
          <p class="blog-summary">${blog.summary || "No summary available."}</p>
          <div class="blog-actions">
            <a class="blog-link secondary" href="${detailHref}">View details</a>
          </div>
        </div>
      </article>
    `;
  }).join("");
}

function renderBlogDetail(blog, dbTarget) {
  setText("detail-title", blog.title || "Untitled blog");
  setText("detail-summary", blog.summary || "No summary available.");
  setText("detail-category", blog.category_name || "Uncategorized");
  setText("detail-created", blog.created_at || "-");
  setText("detail-db", dbTarget?.publish_db_name || "-");

  const media = document.getElementById("detail-media");
  const actions = document.getElementById("detail-actions");
  const content = document.getElementById("detail-content");
  const previewImageUrl = resolvePreviewImageUrl(blog);

  if (media) {
    media.innerHTML = previewImageUrl
      ? `<img src="${previewImageUrl}" alt="${blog.title || "Blog image"}">`
      : `<div class="empty-state">No image available.</div>`;
  }

  if (actions) {
    const links = [];
    if (blog.source_url) {
      links.push(`<a class="blog-link secondary" href="${blog.source_url}" target="_blank" rel="noreferrer">Source</a>`);
    }
    actions.innerHTML = links.join("") || `<div class="empty-state">No external links available.</div>`;
  }

  if (content) {
    const articleBody = `<article class="article-body">${renderArticleContent(blog.content)}</article>`;
    content.innerHTML = articleBody;
  }
}

function initWorkflowPage() {
  const links = Array.from(document.querySelectorAll(".workflow-toc-link"));
  if (!links.length) {
    return;
  }

  const sections = links
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  if (!sections.length) {
    return;
  }

  const setActiveLink = (id) => {
    links.forEach((link) => {
      const isActive = link.getAttribute("href") === `#${id}`;
      link.classList.toggle("active", isActive);
      if (isActive) {
        link.setAttribute("aria-current", "true");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  };

  const updateActiveSection = () => {
    const offset = 180;
    let currentId = sections[0].id;

    sections.forEach((section) => {
      if (section.getBoundingClientRect().top <= offset) {
        currentId = section.id;
      }
    });

    setActiveLink(currentId);
  };

  window.addEventListener("scroll", updateActiveSection, { passive: true });
  window.addEventListener("resize", updateActiveSection);

  const hash = window.location.hash ? window.location.hash.slice(1) : "";
  if (hash && sections.some((section) => section.id === hash)) {
    setActiveLink(hash);
  } else {
    updateActiveSection();
  }
}

async function loadDashboard() {
  const response = await fetch("/api/dashboard");
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Failed to load dashboard data.");
  }
  const snapshot = payload.snapshot || {};
  const stats = snapshot.stats || {};
  setText("db-mode", snapshot.db_target?.status_label || `${snapshot.db_target?.mode || "Unknown"} database`);
  setText("db-host", snapshot.db_target?.host || "-");
  setText("generated-at", payload.generated_at || "-");
  renderMetricCards(stats);
  renderBarChart("activity-chart", snapshot.charts?.activity_by_day || [], dashboardChartSeries());
  renderBarChart("token-chart", snapshot.charts?.tokens_by_day || [], tokenChartSeries());
  renderRuns(snapshot.runs || []);
  renderLogs(snapshot.logs || []);
  renderMemory(snapshot.memory || []);
}

async function loadBlogs() {
  const response = await fetch("/api/blogs?limit=12");
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Failed to load blogs.");
  }
  setText("blog-db-name", payload.db_target?.publish_db_name || "-");
  setText("blog-db-host", payload.db_target?.host || "-");
  setText("blog-generated-at", payload.generated_at || "-");
  renderBlogs(payload.blogs || []);
}

async function loadBlogDetail() {
  const params = new URLSearchParams(window.location.search);
  const slug = params.get("slug");
  if (!slug) {
    throw new Error("Missing blog slug.");
  }
  const response = await fetch(`/api/blog?slug=${encodeURIComponent(slug)}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Failed to load blog.");
  }
  renderBlogDetail(payload.blog || {}, payload.db_target || {});
}

async function init() {
  const page = document.body.dataset.page;
  initThemeToggle();
  try {
    if (page === "dashboard") {
      await loadDashboard();
    } else if (page === "blogs") {
      await loadBlogs();
    } else if (page === "blog-detail") {
      await loadBlogDetail();
    } else if (
      page === "blog-workflow" ||
      page === "agent-adoption-guide" ||
      page === "run-guide"
    ) {
      initWorkflowPage();
    }
  } catch (error) {
    const target = document.getElementById(
      page === "blogs" ? "blog-grid" : page === "blog-detail" ? "detail-content" : "metric-cards"
    );
    if (target) {
      target.innerHTML = `<div class="empty-state">${error.message}</div>`;
    }
  }
}

init();
