import React, { useEffect, useState, useRef } from 'react';
import './App.css';
import {
  adminLogin,
  chatAI,
  fetchAdminProfile,
  fetchAuditLogs,
  fetchCollectionRuns,
  fetchConfiguredSources,
  fetchDepartments,
  fetchHomepageSections,
  fetchMonitoringStats,
  fetchSchemeChanges,
  fetchSchemeDetail,
  fetchSchemes,
  fetchSummary,
  reviewScheme,
  reviewSchemeChange,
  triggerMonitoringScan,
} from './api';
import { t } from './translations';
import type {
  AdminUser,
  AIResponse,
  AuditLogItem,
  CollectionRunItem,
  ConfiguredSourceItem,
  DepartmentInfo,
  HomepageSectionGroup,
  Language,
  SchemeChangeItem,
  SchemeDetail,
  SchemeItem,
  SchemeSummary,
} from './types';

function renderFormattedContent(text: string, isUser: boolean = false) {
  if (!text) return null;
  const lines = text.split('\n');

  function renderInline(str: string) {
    const regex = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
    const parts = str.split(regex);
    return parts.map((part, idx) => {
      if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
        return <strong key={idx}>{part.slice(2, -2)}</strong>;
      }
      const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch) {
        return (
          <a
            key={idx}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: isUser ? '#bfdbfe' : '#2563eb', textDecoration: 'underline', fontWeight: 600 }}
          >
            {linkMatch[1]}
          </a>
        );
      }
      return <span key={idx}>{part}</span>;
    });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', color: isUser ? '#ffffff' : '#1e293b' }}>
      {lines.map((line, lIdx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={lIdx} style={{ height: '0.35rem' }} />;
        }
        if (/^(\d+\.|\*\*\d+\.)/.test(trimmed)) {
          return (
            <div
              key={lIdx}
              style={{
                marginTop: '0.85rem',
                marginBottom: '0.3rem',
                fontSize: '0.98rem',
                fontWeight: 700,
                color: isUser ? '#ffffff' : '#0f172a',
                borderLeft: isUser ? '3px solid #60a5fa' : '3px solid #ff7722',
                paddingLeft: '0.65rem',
                background: isUser ? 'rgba(255, 255, 255, 0.15)' : '#f8fafc',
                padding: '0.4rem 0.65rem',
                borderRadius: '0 8px 8px 0',
              }}
            >
              {renderInline(line)}
            </div>
          );
        }
        if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
          return (
            <div key={lIdx} style={{ display: 'flex', gap: '0.45rem', paddingLeft: '0.4rem', marginBottom: '0.15rem' }}>
              <span style={{ color: isUser ? '#fde047' : '#ff7722', fontWeight: 'bold' }}>•</span>
              <div style={{ flex: 1, color: isUser ? '#ffffff' : '#334155' }}>{renderInline(trimmed.slice(2))}</div>
            </div>
          );
        }
        return <div key={lIdx} style={{ color: isUser ? '#ffffff' : '#1e293b' }}>{renderInline(line)}</div>;
      })}
    </div>
  );
}

export default function App() {
  const [lang, setLang] = useState<Language>('en');
  const strings = t[lang];

  // Navigation state
  const [activeTab, setActiveTab] = useState<'home' | 'schemes' | 'categories' | 'ai' | 'about' | 'admin'>('home');

  // Summary, department and official source metrics
  const [summary, setSummary] = useState<SchemeSummary | null>(null);
  const [departments, setDepartments] = useState<DepartmentInfo[]>([]);
  const [publicSources, setPublicSources] = useState<ConfiguredSourceItem[]>([]);
  const [homepageSections, setHomepageSections] = useState<Record<string, HomepageSectionGroup>>({});
  const [isLoadingSections, setIsLoadingSections] = useState(false);

  // Scheme Explorer state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDept, setSelectedDept] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [selectedDeadlineStatus, setSelectedDeadlineStatus] = useState('');
  const [sortBy, setSortBy] = useState('id_desc');
  const [page, setPage] = useState(0);
  const pageSize = 12;

  const [schemes, setSchemes] = useState<SchemeItem[]>([]);
  const [totalSchemes, setTotalSchemes] = useState(0);
  const [isLoadingSchemes, setIsLoadingSchemes] = useState(false);
  const [schemeError, setSchemeError] = useState<string | null>(null);

  // Scheme Detail Modal state
  const [selectedSchemeId, setSelectedSchemeId] = useState<number | null>(null);
  const [schemeDetail, setSchemeDetail] = useState<SchemeDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  // Scheme Contextual Temporary Chat Modal state
  const [contextualScheme, setContextualScheme] = useState<SchemeItem | null>(null);
  const [contextualMessages, setContextualMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string }>>([]);
  const [contextualInput, setContextualInput] = useState('');
  const [isContextualLoading, setIsContextualLoading] = useState(false);

  // General AI Assistant state
  const [aiQuestion, setAiQuestion] = useState('');
  const [aiChatHistory, setAiChatHistory] = useState<Array<{ role: 'user' | 'assistant'; text: string; response?: AIResponse }>>([
    {
      role: 'assistant',
      text:
        lang === 'mr'
          ? 'नमस्कार! मी महासेवा एआय नागरिक साहाय्यक आहे. आपण महाराष्ट्र शासनाच्या योजनांबद्दल, चालू अर्ज मुदतीबद्दल किंवा आवश्यक कागदपत्रांबद्दल कोणताही प्रश्न विचारू शकता.'
          : 'Welcome! I am your MahaSeva AI Citizen Assistant. Ask me any question regarding Maharashtra state schemes, active deadlines, eligibility rules, or required documents.',
    },
  ]);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const chatMessagesEndRef = useRef<HTMLDivElement>(null);
  const contextualMessagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [aiChatHistory, isAiLoading]);

  useEffect(() => {
    contextualMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [contextualMessages, isContextualLoading]);

  // Admin Portal state
  const [adminToken, setAdminToken] = useState<string | null>(localStorage.getItem('mahaseva_admin_token'));
  const [adminUser, setAdminUser] = useState<AdminUser | null>(null);
  const [adminUsernameInput, setAdminUsernameInput] = useState('');
  const [adminPasswordInput, setAdminPasswordInput] = useState('');
  const [adminLoginError, setAdminLoginError] = useState<string | null>(null);
  const [adminViewTab, setAdminViewTab] = useState<'review' | 'changes' | 'audit' | 'sources'>('review');

  // Admin Review Modal state
  const [reviewingScheme, setReviewingScheme] = useState<SchemeDetail | null>(null);
  const [reviewStatus, setReviewStatus] = useState<string>('verified');
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [reviewBriefDesc, setReviewBriefDesc] = useState<string>('');
  const [reviewBenefits, setReviewBenefits] = useState<string>('');
  const [reviewEligibility, setReviewEligibility] = useState<string>('');
  const [reviewDocs, setReviewDocs] = useState<string>('');
  const [reviewApplyUrl, setReviewApplyUrl] = useState<string>('');
  const [reviewCategory, setReviewCategory] = useState<string>('General');
  const [reviewDeadline, setReviewDeadline] = useState<string>('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  // Admin Audit, Changes & Sources state
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [changesList, setChangesList] = useState<SchemeChangeItem[]>([]);
  const [collectionRuns, setCollectionRuns] = useState<CollectionRunItem[]>([]);
  const [sourcesList, setSourcesList] = useState<ConfiguredSourceItem[]>([]);
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null);
  const [syncStatusMsg, setSyncStatusMsg] = useState<string | null>(null);

  // Initial data loading
  useEffect(() => {
    loadSummary();
    loadDepartments();
    loadHomepageSections();
    loadPublicSources();
  }, []);

  useEffect(() => {
    loadSchemes();
  }, [searchQuery, selectedDept, selectedCategory, selectedStatus, selectedDeadlineStatus, sortBy, page]);

  // Check admin session
  useEffect(() => {
    if (adminToken) {
      fetchAdminProfile()
        .then((user) => setAdminUser(user))
        .catch(() => {
          localStorage.removeItem('mahaseva_admin_token');
          setAdminToken(null);
          setAdminUser(null);
        });
    }
  }, [adminToken]);

  async function loadSummary() {
    try {
      const data = await fetchSummary();
      setSummary(data);
    } catch (err) {
      console.warn('Could not fetch summary metrics:', err);
    }
  }

  async function loadDepartments() {
    try {
      const data = await fetchDepartments();
      setDepartments(data);
    } catch (err) {
      console.warn('Could not fetch departments:', err);
    }
  }

  async function loadHomepageSections() {
    setIsLoadingSections(true);
    try {
      const sections = await fetchHomepageSections();
      setHomepageSections(sections);
    } catch (err) {
      console.warn('Could not fetch homepage sections:', err);
    } finally {
      setIsLoadingSections(false);
    }
  }

  async function loadPublicSources() {
    try {
      const data = await fetchConfiguredSources();
      setPublicSources(data);
    } catch (err) {
      console.warn('Could not fetch public sources:', err);
    }
  }

  async function loadSchemes() {
    setIsLoadingSchemes(true);
    setSchemeError(null);
    try {
      const res = await fetchSchemes({
        q: searchQuery,
        department: selectedDept,
        category: selectedCategory,
        verification_status: selectedStatus,
        deadline_status: selectedDeadlineStatus,
        sort_by: sortBy,
        limit: pageSize,
        offset: page * pageSize,
      });
      setSchemes(res.items);
      setTotalSchemes(res.total);
    } catch (err: any) {
      setSchemeError(err.message || 'Failed to load schemes from server');
    } finally {
      setIsLoadingSchemes(false);
    }
  }

  async function handleOpenDetail(schemeId: number) {
    setSelectedSchemeId(schemeId);
    setIsLoadingDetail(true);
    try {
      const detail = await fetchSchemeDetail(schemeId);
      setSchemeDetail(detail);
    } catch (err) {
      console.error('Failed to load scheme detail:', err);
    } finally {
      setIsLoadingDetail(false);
    }
  }

  function handleOpenContextualChat(scheme: SchemeItem) {
    setContextualScheme(scheme);
    const title = lang === 'mr' && scheme.title_mr ? scheme.title_mr : scheme.title;
    const deadlineText =
      scheme.current_window_status === 'no_deadline_published'
        ? strings.noDeadlineNotice
        : scheme.application_deadline
        ? `${strings.cardDeadline}: ${scheme.application_deadline}`
        : '';
    const statusText = lang === 'mr' && scheme.status_label_mr ? scheme.status_label_mr : scheme.status_label_en || '';

    setContextualMessages([
      {
        role: 'assistant',
        text:
          lang === 'mr'
            ? `नमस्कार! मी **${title}** या योजनेबद्दल माहिती देण्यासाठी उपलब्ध आहे.\n\n- **अर्जाची स्थिती:** ${statusText}\n${deadlineText ? `- ${deadlineText}\n` : ''}\nआपण या योजनेची पात्रता, कागदपत्रे, किंवा अर्ज पद्धतीबद्दल विचारू शकता.`
            : `Hello! I am ready to assist you specifically with **${title}**.\n\n- **Application Status:** ${statusText}\n${deadlineText ? `- ${deadlineText}\n` : ''}\nYou can ask about eligibility requirements, required documents, or how to apply.`,
      },
    ]);
    setContextualInput('');
  }

  function handleCloseContextualChat() {
    setContextualScheme(null);
    setContextualMessages([]);
    setContextualInput('');
  }

  function handleNavChange(tab: 'home' | 'schemes' | 'categories' | 'ai' | 'about' | 'admin') {
    handleCloseContextualChat();
    setActiveTab(tab);
  }

  async function handleSendContextualText(queryText: string) {
    if (!contextualScheme || !queryText.trim() || isContextualLoading) return;

    const userMsg = queryText.trim();
    const updatedMessages = [...contextualMessages, { role: 'user' as const, text: userMsg }];
    setContextualMessages(updatedMessages);
    setContextualInput('');
    setIsContextualLoading(true);

    try {
      const historyPayload = updatedMessages.map((m) => ({
        role: m.role,
        content: m.text,
      }));
      const resp = await chatAI(userMsg, contextualScheme.id, historyPayload, lang);
      setContextualMessages((prev) => [...prev, { role: 'assistant', text: resp.answer }]);
    } catch (err: any) {
      setContextualMessages((prev) => [
        ...prev,
        { role: 'assistant', text: `⚠️ ${err.message || 'Could not retrieve guidance for this scheme.'}` },
      ]);
    } finally {
      setIsContextualLoading(false);
    }
  }

  async function handleSendContextualQuery(e: React.FormEvent) {
    e.preventDefault();
    if (!contextualInput.trim() || isContextualLoading) return;
    handleSendContextualText(contextualInput);
  }

  async function handleAskAI(questionOverride?: string) {
    const q = questionOverride || aiQuestion;
    if (!q.trim() || isAiLoading) return;

    const userMsg = { role: 'user' as const, text: q };
    const updatedHistory = [...aiChatHistory, userMsg];
    setAiChatHistory(updatedHistory);
    if (!questionOverride) setAiQuestion('');
    setIsAiLoading(true);

    try {
      const historyPayload = updatedHistory.map((m) => ({
        role: m.role,
        content: m.text,
      }));
      const response = await chatAI(q, undefined, historyPayload, lang);
      setAiChatHistory((prev) => [
        ...prev,
        { role: 'assistant', text: response.answer, response },
      ]);
    } catch (err: any) {
      setAiChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `⚠️ Error: ${err.message || 'Assistant service is momentarily unavailable.'}`,
        },
      ]);
    } finally {
      setIsAiLoading(false);
    }
  }

  async function handleAdminLogin(e: React.FormEvent) {
    e.preventDefault();
    setAdminLoginError(null);
    try {
      const res = await adminLogin(adminUsernameInput, adminPasswordInput);
      localStorage.setItem('mahaseva_admin_token', res.access_token);
      setAdminToken(res.access_token);
      const user = await fetchAdminProfile();
      setAdminUser(user);
      setAdminUsernameInput('');
      setAdminPasswordInput('');
    } catch (err: any) {
      setAdminLoginError(err.message || 'Login failed. Please check credentials.');
    }
  }

  function handleAdminLogout() {
    localStorage.removeItem('mahaseva_admin_token');
    setAdminToken(null);
    setAdminUser(null);
  }

  async function loadAdminData() {
    if (!adminToken) return;
    try {
      if (adminViewTab === 'changes') {
        const changes = await fetchSchemeChanges();
        setChangesList(changes);
      } else if (adminViewTab === 'audit') {
        const logs = await fetchAuditLogs();
        setAuditLogs(logs);
      } else if (adminViewTab === 'sources') {
        const [runs, sources, stats] = await Promise.all([
          fetchCollectionRuns(),
          fetchConfiguredSources(),
          fetchMonitoringStats(),
        ]);
        setCollectionRuns(runs);
        setSourcesList(sources);
        setSchedulerStatus(stats);
      }
    } catch (err) {
      console.warn('Error loading admin tab data:', err);
    }
  }

  useEffect(() => {
    if (activeTab === 'admin' && adminToken) {
      loadAdminData();
    }
  }, [activeTab, adminToken, adminViewTab]);

  function openReviewModal(scheme: SchemeItem) {
    fetchSchemeDetail(scheme.id).then((full) => {
      setReviewingScheme(full);
      setReviewStatus(full.verification_status);
      setReviewNotes('');
      setReviewBriefDesc(full.brief_description || '');
      setReviewBenefits(full.benefits || '');
      setReviewEligibility(full.eligibility || '');
      setReviewDocs(full.documents_required || '');
      setReviewApplyUrl(full.official_apply_url || '');
      setReviewCategory(full.category || 'General');
      setReviewDeadline(full.application_deadline || '');
    });
  }

  async function handleSaveReview(e: React.FormEvent) {
    e.preventDefault();
    if (!reviewingScheme) return;
    setIsSubmittingReview(true);
    try {
      await reviewScheme(reviewingScheme.id, {
        verification_status: reviewStatus,
        notes: reviewNotes,
        brief_description: reviewBriefDesc,
        benefits: reviewBenefits,
        eligibility: reviewEligibility,
        documents_required: reviewDocs,
        official_apply_url: reviewApplyUrl,
        category: reviewCategory,
        application_deadline: reviewDeadline || undefined,
      });
      setReviewingScheme(null);
      loadSchemes();
      loadSummary();
      loadHomepageSections();
    } catch (err: any) {
      alert(`Update failed: ${err.message}`);
    } finally {
      setIsSubmittingReview(false);
    }
  }

  async function handleReviewChange(changeId: number, statusDecision: 'approved' | 'rejected') {
    try {
      await reviewSchemeChange(changeId, statusDecision);
      const updated = await fetchSchemeChanges();
      setChangesList(updated);
      loadHomepageSections();
      loadSchemes();
    } catch (err: any) {
      alert(`Action failed: ${err.message}`);
    }
  }

  async function handleTriggerScan() {
    setSyncStatusMsg('Triggering monitoring scan...');
    try {
      await triggerMonitoringScan();
      setSyncStatusMsg('Monitoring pass executed. Refreshing records...');
      loadAdminData();
      loadHomepageSections();
      loadSummary();
      loadSchemes();
    } catch (err: any) {
      setSyncStatusMsg(`Scan trigger failed: ${err.message}`);
    }
  }

  // Render Scheme Card
  function renderSchemeCard(scheme: SchemeItem) {
    const title = lang === 'mr' && scheme.title_mr ? scheme.title_mr : scheme.title;
    const statusLabel = lang === 'mr' && scheme.status_label_mr ? scheme.status_label_mr : scheme.status_label_en || scheme.current_window_status;

    let dateBoxClass = 'card-date-meta';
    if (scheme.current_window_status === 'no_deadline_published') {
      dateBoxClass += ' no-deadline';
    } else if (scheme.current_window_status === 'closing_soon') {
      dateBoxClass += ' closing-soon-box';
    } else if (scheme.current_window_status === 'closed') {
      dateBoxClass += ' closed-box';
    }

    return (
      <div key={scheme.id} className="scheme-card">
        <div>
          <div className="card-badges">
            <span className={`status-badge ${scheme.badge_class || 'status-open'}`}>
              ● {statusLabel}
            </span>
            <span className="badge badge-dept">{scheme.category || 'General'}</span>
            {scheme.verification_status === 'verified' ? (
              <span className="badge badge-verified">✓ {strings.badgeVerified}</span>
            ) : (
              <span className="badge badge-pending">⏳ {strings.badgePending}</span>
            )}
          </div>

          <h4 className="scheme-title" title={title}>
            {title}
          </h4>

          <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '0.5rem' }}>
            🏛️ {scheme.department}
          </div>

          {/* Date & Deadline Meta Box */}
          <div className={dateBoxClass}>
            {scheme.current_window_status === 'no_deadline_published' ? (
              <span>ℹ️ {strings.noDeadlineNotice}</span>
            ) : scheme.application_deadline ? (
              <span>
                📅 <strong>{strings.cardDeadline}:</strong> {scheme.application_deadline}
                {scheme.closing_time ? ` (${scheme.closing_time})` : ''}
              </span>
            ) : (
              <span>ℹ️ {strings.noDeadlineNotice}</span>
            )}
            {scheme.last_checked_at && (
              <span style={{ fontSize: '0.72rem', opacity: 0.8 }}>
                Verified check: {scheme.last_checked_at.slice(0, 10)}
              </span>
            )}
          </div>

          <p className="scheme-snippet">
            {scheme.brief_description || scheme.benefits || ''}
          </p>
        </div>

        <div>
          <div className="card-actions-row">
            <button
              className="btn-ask-scheme"
              onClick={() => handleOpenContextualChat(scheme)}
              title={strings.btnAskAboutScheme}
            >
              💬 {strings.btnAskAboutScheme}
            </button>

            <button
              className="btn-details"
              onClick={() => handleOpenDetail(scheme.id)}
            >
              {strings.btnViewDetails} →
            </button>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.75rem' }}>
            {scheme.official_apply_url ? (
              <a
                href={scheme.official_apply_url}
                target="_blank"
                rel="noreferrer"
                className="btn-apply-badge"
              >
                🚀 {strings.btnApplyNow}
              </a>
            ) : (
              <span />
            )}

            <a
              href={scheme.source_url}
              target="_blank"
              rel="noreferrer"
              className="official-link-icon"
              title="Official Government Source Link"
            >
              🔗 {strings.btnOfficialLink}
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-root">
      {/* Navbar */}
      <header className="navbar">
        <div className="container nav-inner">
          <div className="brand" onClick={() => setActiveTab('home')} style={{ cursor: 'pointer' }}>
            <div className="brand-emblem">🏛️</div>
            <div className="brand-text">
              <h1>{strings.siteTitle}</h1>
              <p>{strings.siteSubtitle}</p>
            </div>
          </div>

          <nav className="nav-links">
            <button
              className={`nav-item ${activeTab === 'home' ? 'active' : ''}`}
              onClick={() => handleNavChange('home')}
            >
              {strings.navHome}
            </button>
            <button
              className={`nav-item ${activeTab === 'schemes' ? 'active' : ''}`}
              onClick={() => handleNavChange('schemes')}
            >
              {strings.navSchemes}
            </button>
            <button
              className={`nav-item ${activeTab === 'categories' ? 'active' : ''}`}
              onClick={() => handleNavChange('categories')}
            >
              📑 {strings.navCategories}
            </button>
            <button
              className={`nav-item ${activeTab === 'ai' ? 'active' : ''}`}
              onClick={() => handleNavChange('ai')}
            >
              ✨ {strings.navAssistant}
            </button>
            <button
              className={`nav-item ${activeTab === 'about' ? 'active' : ''}`}
              onClick={() => handleNavChange('about')}
            >
              ℹ️ {strings.navAbout}
            </button>

            {adminUser ? (
              <button
                className={`admin-nav-btn ${activeTab === 'admin' ? 'active' : ''}`}
                onClick={() => handleNavChange('admin')}
              >
                🛡️ {adminUser.username}
              </button>
            ) : (
              <button
                className={`admin-nav-btn ${activeTab === 'admin' ? 'active' : ''}`}
                onClick={() => handleNavChange('admin')}
              >
                🔒 {strings.navAdmin}
              </button>
            )}

            <div className="lang-toggle">
              <button
                className={`lang-btn ${lang === 'en' ? 'active' : ''}`}
                onClick={() => setLang('en')}
              >
                EN
              </button>
              <button
                className={`lang-btn ${lang === 'mr' ? 'active' : ''}`}
                onClick={() => setLang('mr')}
              >
                मराठी
              </button>
            </div>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section className="hero">
        <div className="container">
          <div className="hero-badge">🏛️ {strings.heroBadge}</div>
          <h2>{strings.heroHeading}</h2>
          <p className="hero-desc">{strings.heroDesc}</p>

          <form
            className="hero-search-box"
            onSubmit={(e) => {
              e.preventDefault();
              setPage(0);
              setTimeout(() => {
                const target = document.getElementById('homepage-search-results') || document.getElementById('all-schemes-directory');
                if (target) {
                  target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
              }, 50);
            }}
          >
            <input
              type="text"
              className="hero-search-input"
              placeholder={strings.searchPlaceholder}
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(0);
              }}
            />
            {searchQuery && (
              <button
                type="button"
                className="hero-search-clear-btn"
                title={lang === 'mr' ? 'शोध साफ करा' : 'Clear search'}
                onClick={() => {
                  setSearchQuery('');
                  setPage(0);
                }}
              >
                ✕
              </button>
            )}
            <button type="submit" className="hero-search-btn">
              🔍 {strings.btnSearch}
            </button>
          </form>

          {/* Quick Metrics */}
          <div className="stats-row">
            <div className="stat-card">
              <div className="stat-number">{summary ? summary.total_candidates : '174+'}</div>
              <div className="stat-label">{strings.statTotal}</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{summary ? summary.verified_count : '6+'}</div>
              <div className="stat-label">{strings.statVerified}</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{departments.length || 6}</div>
              <div className="stat-label">{strings.statDepartments}</div>
            </div>
          </div>

          {/* Category filter pills */}
          <div className="category-pills">
            {[
              { id: '', label: strings.catAll },
              { id: 'Agriculture', label: strings.catFarmers },
              { id: 'Social Justice & Welfare', label: strings.catSocial },
              { id: 'Women & Child', label: strings.catWomen },
              { id: 'Co-operation & Textiles', label: lang === 'mr' ? 'सहकार व वस्त्रोद्योग' : 'Co-operation & Textiles' },
              { id: 'Urban Development', label: strings.catUrban },
            ].map((cat) => (
              <button
                key={cat.id}
                className={`pill-btn ${selectedCategory === cat.id ? 'active' : ''}`}
                onClick={() => {
                  setSelectedCategory(cat.id === selectedCategory ? '' : cat.id);
                  setPage(0);
                  setTimeout(() => {
                    const target = document.getElementById('homepage-search-results') || document.getElementById('all-schemes-directory');
                    if (target) {
                      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                  }, 50);
                }}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Main Content Area based on Tab */}
      <main className="container" style={{ minHeight: '600px', paddingBottom: '4rem' }}>
        {/* TAB 1: HOME (Dynamic Sections Loaded From Database) */}
        {activeTab === 'home' && (
          <div className="homepage-sections-container">
            {isLoadingSections ? (
              <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                <p>Loading authoritative Maharashtra government scheme listings...</p>
              </div>
            ) : (searchQuery.trim() || selectedCategory) ? (
              /* Dedicated Live Search & Category Results Section on Home Page */
              <div className="homepage-section-block" id="homepage-search-results" style={{ animation: 'fadeIn 0.3s ease-in' }}>
                <div className="section-headline" style={{ flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
                  <div className="section-title-wrap">
                    <h3>
                      🔍 {searchQuery.trim()
                        ? (lang === 'mr' ? `"${searchQuery}" साठी शोध निकाल` : `Search Results for "${searchQuery}"`)
                        : (lang === 'mr' ? `वर्गवारी: ${selectedCategory}` : `Category: ${selectedCategory}`)}
                    </h3>
                    <span className="section-pill-count" style={{ background: '#f26419' }}>
                      {totalSchemes} {lang === 'mr' ? 'योजना' : 'schemes'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                      className="btn-details"
                      style={{ background: '#f1f5f9', color: '#334155', border: '1px solid #cbd5e1' }}
                      onClick={() => {
                        setSearchQuery('');
                        setSelectedCategory('');
                        setPage(0);
                      }}
                    >
                      ✕ {lang === 'mr' ? 'शोध साफ करा' : 'Clear Search'}
                    </button>

                    <button
                      className="btn-details"
                      onClick={() => setActiveTab('schemes')}
                    >
                      {lang === 'mr' ? 'सर्व तपशील पाहा' : 'Open in Explorer'} →
                    </button>
                  </div>
                </div>

                {/* Status filter tabs for search results */}
                <div className="status-tabs" style={{ marginBottom: '1.5rem', flexWrap: 'wrap' }}>
                  {[
                    { id: '', label: lang === 'mr' ? 'सर्व निकाल (All)' : 'All Results' },
                    { id: 'open', label: lang === 'mr' ? '🟢 चालू अर्ज' : '🟢 Open Now' },
                    { id: 'closing_soon', label: lang === 'mr' ? '⚠️ मुदत संपत आहे' : '⚠️ Closing Soon' },
                    { id: 'no_deadline_published', label: lang === 'mr' ? '🟣 मुदत नसलेल्या' : '🟣 No Deadline' },
                    { id: 'upcoming', label: lang === 'mr' ? '🗓️ आगामी' : '🗓️ Upcoming' },
                    { id: 'closed', label: lang === 'mr' ? '🔴 मुदत संपलेल्या' : '🔴 Closed Windows' },
                  ].map((st) => (
                    <button
                      key={st.id}
                      className={`status-tab ${selectedDeadlineStatus === st.id ? 'active' : ''}`}
                      onClick={() => {
                        setSelectedDeadlineStatus(st.id);
                        setPage(0);
                      }}
                    >
                      {st.label}
                    </button>
                  ))}
                </div>

                {isLoadingSchemes ? (
                  <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                    <p>{lang === 'mr' ? 'योजना शोधत आहे...' : 'Searching Maharashtra schemes...'}</p>
                  </div>
                ) : schemes.length === 0 ? (
                  <div className="empty-state" style={{ textAlign: 'center', padding: '3.5rem 1.5rem', background: '#fff', borderRadius: '14px', border: '1px dashed #cbd5e1' }}>
                    <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>🔍</div>
                    <h4 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', color: '#1e293b' }}>
                      {lang === 'mr' ? 'कोणतीही योजना आढळली नाही' : 'No matching schemes found'}
                    </h4>
                    <p style={{ color: '#64748b', maxWidth: '500px', margin: '0 auto 1.5rem', fontSize: '0.95rem' }}>
                      {lang === 'mr'
                        ? `"${searchQuery}" साठी कोणताही निकाल लागला नाही. कृपया वेगळा शब्द टाकून पाहा किंवा शोध साफ करा.`
                        : `No schemes matched "${searchQuery}". Try searching with terms like "farmer", "subsidy", "student", or clear your filter.`}
                    </p>
                    <button
                      className="hero-search-btn"
                      style={{ margin: '0 auto', display: 'inline-flex' }}
                      onClick={() => {
                        setSearchQuery('');
                        setSelectedCategory('');
                        setSelectedDeadlineStatus('');
                        setPage(0);
                      }}
                    >
                      ✕ {lang === 'mr' ? 'शोध साफ करा व सर्व योजना पाहा' : 'Clear search & show all schemes'}
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="schemes-grid">
                      {schemes.map(renderSchemeCard)}
                    </div>

                    {/* Pagination if more than pageSize */}
                    {totalSchemes > pageSize && (
                      <div className="pagination" style={{ marginTop: '2rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem' }}>
                        <button
                          className="page-btn"
                          onClick={() => setPage(Math.max(0, page - 1))}
                          disabled={page === 0}
                          style={{ opacity: page === 0 ? 0.5 : 1 }}
                        >
                          ← {lang === 'mr' ? 'मागील' : 'Previous'}
                        </button>
                        <span className="page-indicator">
                          {lang === 'mr' ? 'पान' : 'Page'} {page + 1} / {Math.ceil(totalSchemes / pageSize)}
                        </span>
                        <button
                          className="page-btn"
                          onClick={() => setPage(page + 1)}
                          disabled={(page + 1) * pageSize >= totalSchemes}
                          style={{ opacity: (page + 1) * pageSize >= totalSchemes ? 0.5 : 1 }}
                        >
                          {lang === 'mr' ? 'पुढील' : 'Next'} →
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : (
              <>
                {/* 1. Applications Open Now */}
                {homepageSections.open_now && homepageSections.open_now.count > 0 && (
                  <div className="homepage-section-block">
                    <div className="section-headline">
                      <div className="section-title-wrap">
                        <h3>🟢 {lang === 'mr' ? homepageSections.open_now.title_mr : homepageSections.open_now.title_en}</h3>
                        <span className="section-pill-count">{homepageSections.open_now.count}</span>
                      </div>
                      <button
                        className="btn-details"
                        onClick={() => {
                          setSelectedDeadlineStatus('open');
                          setActiveTab('schemes');
                        }}
                      >
                        {strings.btnViewDetails} →
                      </button>
                    </div>
                    <div className="schemes-grid">
                      {homepageSections.open_now.items.map(renderSchemeCard)}
                    </div>
                  </div>
                )}

                {/* 2. Closing Soon */}
                {homepageSections.closing_soon && homepageSections.closing_soon.count > 0 && (
                  <div className="homepage-section-block">
                    <div className="section-headline">
                      <div className="section-title-wrap">
                        <h3>⚠️ {lang === 'mr' ? homepageSections.closing_soon.title_mr : homepageSections.closing_soon.title_en}</h3>
                        <span className="section-pill-count" style={{ background: '#d97706' }}>
                          {homepageSections.closing_soon.count}
                        </span>
                      </div>
                      <button
                        className="btn-details"
                        onClick={() => {
                          setSelectedDeadlineStatus('closing_soon');
                          setActiveTab('schemes');
                        }}
                      >
                        {strings.btnViewDetails} →
                      </button>
                    </div>
                    <div className="schemes-grid">
                      {homepageSections.closing_soon.items.map(renderSchemeCard)}
                    </div>
                  </div>
                )}

                {/* 3. Upcoming Schemes */}
                {homepageSections.upcoming && homepageSections.upcoming.count > 0 && (
                  <div className="homepage-section-block">
                    <div className="section-headline">
                      <div className="section-title-wrap">
                        <h3>🗓️ {lang === 'mr' ? homepageSections.upcoming.title_mr : homepageSections.upcoming.title_en}</h3>
                        <span className="section-pill-count" style={{ background: '#2563eb' }}>
                          {homepageSections.upcoming.count}
                        </span>
                      </div>
                      <button
                        className="btn-details"
                        onClick={() => {
                          setSelectedDeadlineStatus('upcoming');
                          setActiveTab('schemes');
                        }}
                      >
                        {strings.btnViewDetails} →
                      </button>
                    </div>
                    <div className="schemes-grid">
                      {homepageSections.upcoming.items.map(renderSchemeCard)}
                    </div>
                  </div>
                )}

                {/* 4. No Deadline Published */}
                {homepageSections.no_deadline && homepageSections.no_deadline.count > 0 && (
                  <div className="homepage-section-block">
                    <div className="section-headline">
                      <div className="section-title-wrap">
                        <h3>ℹ️ {lang === 'mr' ? homepageSections.no_deadline.title_mr : homepageSections.no_deadline.title_en}</h3>
                        <span className="section-pill-count" style={{ background: '#7e22ce' }}>
                          {homepageSections.no_deadline.count}
                        </span>
                      </div>
                      <button
                        className="btn-details"
                        onClick={() => {
                          setSelectedDeadlineStatus('no_deadline_published');
                          setActiveTab('schemes');
                        }}
                      >
                        {strings.btnViewDetails} →
                      </button>
                    </div>
                    <div className="schemes-grid">
                      {homepageSections.no_deadline.items.map(renderSchemeCard)}
                    </div>
                  </div>
                )}

                {/* 5. Recently Announced */}
                {homepageSections.recently_announced && homepageSections.recently_announced.count > 0 && (
                  <div className="homepage-section-block">
                    <div className="section-headline">
                      <div className="section-title-wrap">
                        <h3>✨ {lang === 'mr' ? homepageSections.recently_announced.title_mr : homepageSections.recently_announced.title_en}</h3>
                        <span className="section-pill-count" style={{ background: '#059669' }}>
                          {homepageSections.recently_announced.count}
                        </span>
                      </div>
                    </div>
                    <div className="schemes-grid">
                      {homepageSections.recently_announced.items.map(renderSchemeCard)}
                    </div>
                  </div>
                )}

                {/* 6. Recently Updated */}
                {homepageSections.recently_updated && homepageSections.recently_updated.count > 0 && (
                  <div className="homepage-section-block">
                    <div className="section-headline">
                      <div className="section-title-wrap">
                        <h3>🔄 {lang === 'mr' ? homepageSections.recently_updated.title_mr : homepageSections.recently_updated.title_en}</h3>
                        <span className="section-pill-count" style={{ background: '#0891b2' }}>
                          {homepageSections.recently_updated.count}
                        </span>
                      </div>
                    </div>
                    <div className="schemes-grid">
                      {homepageSections.recently_updated.items.map(renderSchemeCard)}
                    </div>
                  </div>
                )}

                {/* 7. Closed Windows */}
                {homepageSections.closed && homepageSections.closed.count > 0 && (
                  <div className="homepage-section-block">
                    <div className="section-headline">
                      <div className="section-title-wrap">
                        <h3>⌛ {lang === 'mr' ? homepageSections.closed.title_mr : homepageSections.closed.title_en}</h3>
                        <span className="section-pill-count" style={{ background: '#64748b' }}>
                          {homepageSections.closed.count}
                        </span>
                      </div>
                      <button
                        className="btn-details"
                        onClick={() => {
                          setSelectedDeadlineStatus('closed');
                          setActiveTab('schemes');
                        }}
                      >
                        {strings.btnViewDetails} →
                      </button>
                    </div>
                    <div className="schemes-grid">
                      {homepageSections.closed.items.map(renderSchemeCard)}
                    </div>
                  </div>
                )}

                {/* 8. Complete Schemes Directory (All Schemes — Open, Closing Soon, Upcoming, No Deadline, and Closed) */}
                <div className="homepage-section-block" id="all-schemes-directory" style={{ marginTop: '3rem', paddingTop: '2rem', borderTop: '2px solid #e2e8f0' }}>
                  <div className="section-headline">
                    <div className="section-title-wrap">
                      <h3>📚 {lang === 'mr' ? 'सर्व महाराष्ट्र शासन योजना (सर्व स्थिती - चालू व मुदत संपलेल्या)' : 'All Maharashtra Government Schemes (All Statuses — Open, Upcoming & Closed)'}</h3>
                      <span className="section-pill-count" style={{ background: '#07192e' }}>
                        {totalSchemes}
                      </span>
                    </div>
                  </div>
                  <p style={{ color: '#64748b', fontSize: '0.88rem', marginBottom: '1.25rem' }}>
                    {lang === 'mr'
                      ? 'चालू अर्ज, आगामी, अंतिम तारीख नसलेल्या आणि अर्ज मुदत संपलेल्या (Closed) सर्व १७४+ अधिकृत योजनांची संपूर्ण यादी.'
                      : 'Complete verified Maharashtra state scheme catalog including active, upcoming, no published deadline, and closed application windows.'}
                  </p>

                  {/* Status filter tabs directly on homepage */}
                  <div className="status-tabs" style={{ marginBottom: '1.5rem', flexWrap: 'wrap' }}>
                    {[
                      { id: '', label: lang === 'mr' ? 'सर्व योजना (All)' : 'All Schemes' },
                      { id: 'open', label: lang === 'mr' ? '🟢 चालू अर्ज' : '🟢 Open Now' },
                      { id: 'closing_soon', label: lang === 'mr' ? '⚠️ मुदत संपत आहे' : '⚠️ Closing Soon' },
                      { id: 'no_deadline_published', label: lang === 'mr' ? '🟣 मुदत नसलेल्या' : '🟣 No Deadline' },
                      { id: 'upcoming', label: lang === 'mr' ? '🗓️ आगामी' : '🗓️ Upcoming' },
                      { id: 'closed', label: lang === 'mr' ? '🔴 मुदत संपलेल्या (Closed)' : '🔴 Closed Windows' },
                    ].map((st) => (
                      <button
                        key={st.id}
                        className={`status-tab ${selectedDeadlineStatus === st.id ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedDeadlineStatus(st.id);
                          setPage(0);
                        }}
                      >
                        {st.label}
                      </button>
                    ))}
                  </div>

                  {isLoadingSchemes ? (
                    <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                      <p>Loading schemes directory...</p>
                    </div>
                  ) : schemes.length === 0 ? (
                    <div className="empty-state" style={{ textAlign: 'center', padding: '3rem', background: '#fff', borderRadius: '12px' }}>
                      <p>No schemes found matching current filters.</p>
                      <button
                        className="btn-details"
                        style={{ marginTop: '1rem' }}
                        onClick={() => {
                          setSearchQuery('');
                          setSelectedCategory('');
                          setSelectedDeadlineStatus('');
                          setPage(0);
                        }}
                      >
                        Reset Filters
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="schemes-grid">
                        {schemes.map(renderSchemeCard)}
                      </div>

                      {/* Homepage Pagination Controls */}
                      {totalSchemes > pageSize && (
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', marginTop: '2.5rem' }}>
                          <button
                            className="btn-details"
                            disabled={page === 0}
                            onClick={() => setPage((p) => Math.max(0, p - 1))}
                            style={{ opacity: page === 0 ? 0.5 : 1 }}
                          >
                            ← {lang === 'mr' ? 'मागील' : 'Previous'}
                          </button>
                          <span style={{ fontWeight: 600, color: '#334155', fontSize: '0.9rem' }}>
                            {lang === 'mr'
                              ? `पृष्ठ ${page + 1} / ${Math.ceil(totalSchemes / pageSize)} (${totalSchemes} योजना)`
                              : `Page ${page + 1} of ${Math.ceil(totalSchemes / pageSize)} (${totalSchemes} schemes)`}
                          </span>
                          <button
                            className="btn-details"
                            disabled={(page + 1) * pageSize >= totalSchemes}
                            onClick={() => setPage((p) => p + 1)}
                            style={{ opacity: (page + 1) * pageSize >= totalSchemes ? 0.5 : 1 }}
                          >
                            {lang === 'mr' ? 'पुढील' : 'Next'} →
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* TAB 2: SCHEMES EXPLORER */}
        {activeTab === 'schemes' && (
          <section className="explorer-section">
            <div className="explorer-header">
              <div className="explorer-title">
                <h3>{strings.navSchemes}</h3>
                <p>Showing {totalSchemes} official schemes matching current filters</p>
              </div>

              {/* Status filter tabs */}
              <div className="status-tabs">
                {[
                  { id: '', label: strings.filterAll },
                  { id: 'verified', label: strings.filterVerifiedOnly },
                  { id: 'pending_review', label: strings.filterPendingReview },
                ].map((s) => (
                  <button
                    key={s.id}
                    className={`status-tab ${selectedStatus === s.id ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedStatus(s.id);
                      setPage(0);
                    }}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Filter Bar with Search, Deadline and Department */}
            <div className="filter-bar">
              <div className="filter-group" style={{ flex: '1 1 200px' }}>
                <span className="filter-label">🔍 {lang === 'mr' ? 'कीवर्ड शोधा:' : 'Search Keyword:'}</span>
                <input
                  type="text"
                  className="filter-select"
                  placeholder={strings.searchPlaceholder}
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setPage(0);
                  }}
                  style={{ background: '#fff' }}
                />
              </div>

              <div className="filter-group">
                <span className="filter-label">{strings.filterDeadlineLabel}</span>
                <select
                  className="filter-select"
                  value={selectedDeadlineStatus}
                  onChange={(e) => {
                    setSelectedDeadlineStatus(e.target.value);
                    setPage(0);
                  }}
                >
                  <option value="">{strings.filterDeadlineAll}</option>
                  <option value="open">{strings.filterDeadlineOpen}</option>
                  <option value="closing_soon">{strings.filterDeadlineClosing}</option>
                  <option value="upcoming">{strings.filterDeadlineUpcoming}</option>
                  <option value="no_deadline_published">{strings.filterDeadlineNoDeadline}</option>
                  <option value="closed">{strings.filterDeadlineClosed}</option>
                </select>
              </div>

              <div className="filter-group">
                <span className="filter-label">{strings.filterDeptLabel}</span>
                <select
                  className="filter-select"
                  value={selectedDept}
                  onChange={(e) => {
                    setSelectedDept(e.target.value);
                    setPage(0);
                  }}
                >
                  <option value="">{strings.filterAllDepts}</option>
                  {departments.map((d) => (
                    <option key={d.name} value={d.name}>
                      {d.name} ({d.total_schemes})
                    </option>
                  ))}
                </select>
              </div>

              <div className="filter-group">
                <span className="filter-label">{strings.sortByLabel}</span>
                <select
                  className="filter-select"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                >
                  <option value="id_desc">{strings.sortNewest}</option>
                  <option value="deadline_asc">{strings.sortDeadline}</option>
                  <option value="title_asc">{strings.sortAlpha}</option>
                </select>
              </div>
            </div>

            {/* Scheme Cards Grid */}
            {isLoadingSchemes ? (
              <div className="schemes-grid">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div key={i} className="skeleton-card" />
                ))}
              </div>
            ) : schemeError ? (
              <div style={{ textAlign: 'center', padding: '3rem', color: '#b91c1c' }}>
                <p>⚠️ {schemeError}</p>
              </div>
            ) : schemes.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '4rem 1rem', background: '#fff', borderRadius: '14px' }}>
                <h4>{strings.noSchemesFound}</h4>
                <p style={{ color: '#64748b', marginTop: '0.5rem' }}>{strings.noSchemesHelp}</p>
                <button
                  className="btn-details"
                  style={{ marginTop: '1rem' }}
                  onClick={() => {
                    setSearchQuery('');
                    setSelectedDept('');
                    setSelectedCategory('');
                    setSelectedStatus('');
                    setSelectedDeadlineStatus('');
                  }}
                >
                  Reset All Filters
                </button>
              </div>
            ) : (
              <div className="schemes-grid">
                {schemes.map(renderSchemeCard)}
              </div>
            )}

            {/* Pagination */}
            {totalSchemes > pageSize && (
              <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginTop: '2.5rem' }}>
                <button
                  className="btn-details"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  style={{ opacity: page === 0 ? 0.5 : 1 }}
                >
                  ← Previous
                </button>
                <span style={{ display: 'flex', alignItems: 'center', fontWeight: 600, color: '#334155' }}>
                  Page {page + 1} of {Math.ceil(totalSchemes / pageSize)}
                </span>
                <button
                  className="btn-details"
                  disabled={(page + 1) * pageSize >= totalSchemes}
                  onClick={() => setPage((p) => p + 1)}
                  style={{ opacity: (page + 1) * pageSize >= totalSchemes ? 0.5 : 1 }}
                >
                  Next →
                </button>
              </div>
            )}
          </section>
        )}

        {/* TAB: SCHEME CATEGORIES & DEPARTMENTS */}
        {activeTab === 'categories' && (
          <section className="categories-section" style={{ margin: '2rem 0' }}>
            <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
              <div className="hero-badge" style={{ display: 'inline-block', marginBottom: '0.5rem' }}>
                📂 {lang === 'mr' ? 'अधिकृत वर्गवारी मार्गदर्शक' : 'Official Schemes Taxonomy'}
              </div>
              <h2 style={{ fontSize: '2rem', color: 'var(--primary-navy)', fontWeight: 700 }}>
                {strings.categoriesHeading}
              </h2>
              <p style={{ color: '#64748b', marginTop: '0.5rem', maxWidth: '640px', margin: '0.5rem auto 0' }}>
                {lang === 'mr'
                  ? 'महाराष्ट्र शासनाच्या विविध कल्याणकारी विभाग व वर्गवारीनुसार योजना शोधा आणि थेट अर्ज करा.'
                  : 'Explore schemes organized by major Maharashtra state administrative departments and citizen focus areas.'}
              </p>
            </div>

            {/* Curated Category Cards */}
            <div className="schemes-grid" style={{ marginBottom: '3rem' }}>
              {[
                {
                  id: 'Agriculture',
                  titleEn: 'Agriculture & Farmer Welfare',
                  titleMr: 'कृषी व शेतकरी कल्याण',
                  descEn: 'Subsidies, crop insurance, farm ponds, drip irrigation, and mechanization schemes.',
                  descMr: 'शेततळे, ठिबक सिंचन, कृषी यांत्रिकीकरण आणि पीक विमा अनुदान योजना.',
                  icon: '🌾',
                  badge: '60+ Schemes',
                },
                {
                  id: 'Women & Child',
                  titleEn: 'Women & Child Development',
                  titleMr: 'महिला व बालविकास',
                  descEn: 'Mukhyamantri Majhi Ladki Bahin Yojana, Lek Ladki, nutrition, and self-help groups.',
                  descMr: 'मुख्यमंत्री माझी लाडकी बहीण योजना, लेक लाडकी, पोषण आहार व महिला सबलीकरण.',
                  icon: '👩',
                  badge: 'Flagship Active',
                },
                {
                  id: 'Social Justice & Welfare',
                  titleEn: 'Social Justice & Special Assistance',
                  titleMr: 'सामाजिक न्याय व विशेष सहाय्य',
                  descEn: 'Sanjay Gandhi Niradhar, Shravan Bal, financial pensions, and marginalized assistance.',
                  descMr: 'संजय गांधी निराधार, श्रावण बाळ, वृद्ध व दिव्यांग व्यक्तींसाठी पेन्शन व सहाय्य.',
                  icon: '🤝',
                  badge: 'Direct Pensions',
                },
                {
                  id: 'Education & DBT',
                  titleEn: 'Higher Education, Scholarships & DBT',
                  titleMr: 'उच्च शिक्षण, शिष्यवृत्ती व महाडीबीटी',
                  descEn: 'Post-matric scholarships, tuition fee waivers, hostel allowances for students.',
                  descMr: 'महाडीबीटी मॅट्रिकोत्तर शिष्यवृत्ती, शिक्षण शुल्क सवलत व स्वाधार वसतिगृह भत्ता.',
                  icon: '🎓',
                  badge: 'MahaDBT Integrated',
                },
                {
                  id: 'Co-operation & Textiles',
                  titleEn: 'Co-operation, Textiles & Industries',
                  titleMr: 'सहकार, वस्त्रोद्योग व उद्योग',
                  descEn: 'Powerloom subsidies, weaver welfare, self-employment, and cooperative society support.',
                  descMr: 'सूतगिरणी, यंत्रमाग कामगार अनुदान, वीज सवलत व स्वयंरोजगार अर्थसहाय्य योजना.',
                  icon: '🧵',
                  badge: 'Economic Welfare',
                },
                {
                  id: 'Health & Medical',
                  titleEn: 'Public Health & Medical Assistance',
                  titleMr: 'सार्वजनिक आरोग्य व वैद्यकीय मदत',
                  descEn: 'Mahatma Jyotirao Phule Jan Arogya Yojana, cash assistance, and health security.',
                  descMr: 'महात्मा ज्योतिराव फुले जन आरोग्य योजना व मुख्यमंत्री वैद्यकीय सहायता निधी.',
                  icon: '🏥',
                  badge: 'Health Coverage',
                },
              ].map((cat) => (
                <div key={cat.id} className="scheme-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                      <span style={{ fontSize: '2rem' }}>{cat.icon}</span>
                      <span className="badge badge-dept">{cat.badge}</span>
                    </div>
                    <h3 style={{ fontSize: '1.2rem', color: 'var(--primary-navy)', fontWeight: 700, marginBottom: '0.4rem' }}>
                      {lang === 'mr' ? cat.titleMr : cat.titleEn}
                    </h3>
                    <p style={{ color: '#64748b', fontSize: '0.88rem', lineHeight: 1.5, marginBottom: '1rem' }}>
                      {lang === 'mr' ? cat.descMr : cat.descEn}
                    </p>
                  </div>
                  <button
                    className="btn-details"
                    style={{ width: '100%', justifyContent: 'center' }}
                    onClick={() => {
                      setSelectedCategory(cat.id);
                      setSearchQuery('');
                      setPage(0);
                      setActiveTab('schemes');
                    }}
                  >
                    {lang === 'mr' ? 'या वर्गवारीतील योजना पाहा' : 'Explore Category Schemes'} →
                  </button>
                </div>
              ))}
            </div>

            {/* Department Directory List */}
            <div style={{ background: '#ffffff', borderRadius: '16px', border: '1px solid #cbd5e1', padding: '2rem' }}>
              <h3 style={{ fontSize: '1.3rem', color: 'var(--primary-navy)', fontWeight: 700, marginBottom: '1rem' }}>
                🏛️ {lang === 'mr' ? 'महाराष्ट्र शासन विभाग यादी' : 'Maharashtra Government Departments'}
              </h3>
              <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                {lang === 'mr'
                  ? 'खालीलपैकी कोणत्याही विभागावर क्लिक करून त्या विभागाच्या पडताळणी झालेल्या योजना पाहा.'
                  : 'Click on any registered Maharashtra Government department below to filter all its verified schemes.'}
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
                {departments.map((dept) => (
                  <div
                    key={dept.name}
                    onClick={() => {
                      setSelectedDept(dept.name);
                      setSelectedCategory('');
                      setSearchQuery('');
                      setPage(0);
                      setActiveTab('schemes');
                    }}
                    style={{
                      padding: '1rem 1.25rem',
                      border: '1px solid #e2e8f0',
                      borderRadius: '10px',
                      cursor: 'pointer',
                      background: '#f8fafc',
                      transition: 'all 0.2s ease',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ fontWeight: 600, color: '#1e293b', fontSize: '0.9rem' }}>
                      🏛️ {dept.name}
                    </span>
                    <span className="section-pill-count" style={{ background: '#2563eb', fontSize: '0.75rem' }}>
                      {dept.total_schemes}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* TAB 3: AI CITIZEN ASSISTANT */}
        {activeTab === 'ai' && (
          <section style={{ maxWidth: '840px', margin: '2rem auto' }}>
            <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
              <h2 style={{ fontSize: '2rem', color: 'var(--primary-navy)', fontWeight: 700 }}>
                ✨ {strings.aiHeading}
              </h2>
              <p style={{ color: '#64748b', marginTop: '0.5rem' }}>{strings.aiDesc}</p>
              <div style={{ fontSize: '0.8rem', color: '#047857', marginTop: '0.4rem', fontWeight: 600 }}>
                🔒 {strings.aiPrivacyNotice}
              </div>
            </div>

            {/* Quick Schemes & Action Toolbar */}
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  ⚡ {lang === 'mr' ? 'लोकप्रिय शासकीय योजना शोधा:' : 'Popular Flagship Scheme Topics:'}
                </span>

                <button
                  type="button"
                  className="btn-details"
                  style={{ background: '#f8fafc', color: '#475569', border: '1px solid #cbd5e1', fontSize: '0.8rem', padding: '0.3rem 0.75rem' }}
                  title="Reset temporary chat session"
                  onClick={() => {
                    setAiChatHistory([
                      {
                        role: 'assistant',
                        text:
                          lang === 'mr'
                            ? 'नमस्कार! मी महासेवा एआय नागरिक साहाय्यक आहे. आपण महाराष्ट्र शासनाच्या योजनांबद्दल, चालू अर्ज मुदतीबद्दल किंवा आवश्यक कागदपत्रांबद्दल कोणताही प्रश्न विचारू शकता.'
                            : 'Welcome! I am your MahaSeva AI Citizen Assistant. Ask me any question regarding Maharashtra state schemes, active deadlines, eligibility rules, or required documents.',
                      },
                    ]);
                    setAiQuestion('');
                  }}
                >
                  🔄 {strings.btnNewChat}
                </button>
              </div>

              {/* Topic chips */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
                {[
                  { label: '🌸 Majhi Ladki Bahin', query: 'Mukhyamantri Majhi Ladki Bahin Yojana eligibility and benefits' },
                  { label: '🎓 Student Scholarships', query: 'Student Scholarships in Maharashtra' },
                  { label: '🌾 Farmer Subsidy & Loans', query: 'Farmer loan waiver and agriculture subsidy schemes' },
                  { label: '⚡ Baliraja Free Electricity', query: 'Mukhyamantri Baliraja Vij Savalat Yojana 7.5 HP' },
                  { label: '🏠 Gharkul Housing', query: 'Ramai and Shabari Gharkul housing schemes' },
                  { label: '🏥 Free Health ₹5 Lakh', query: 'Mahatma Jyotirao Phule Jan Arogya Yojana MJPJAY' },
                  { label: '👵 Senior Pension', query: 'Shravan Bal Pension and Vayoshri Yojana' },
                  { label: '🌐 मराठीत सांगा', query: 'give in marathi' },
                ].map((chip, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="pill-btn"
                    onClick={() => handleAskAI(chip.query)}
                    style={{ fontSize: '0.8rem', background: '#f1f5f9', color: '#1e293b', border: '1px solid #cbd5e1' }}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Chat Box */}
            <div
              style={{
                background: '#ffffff',
                border: '1px solid #cbd5e1',
                borderRadius: '16px',
                padding: '1.5rem',
                minHeight: '420px',
                display: 'flex',
                flexDirection: 'column',
                gap: '1.25rem',
                boxShadow: '0 8px 30px rgba(0,0,0,0.06)',
              }}
            >
              <div style={{ flex: 1, minHeight: '340px', maxHeight: '560px', display: 'flex', flexDirection: 'column', gap: '1.1rem', overflowY: 'auto', paddingRight: '0.35rem' }}>
                {aiChatHistory.map((msg, i) => {
                  const isAssistant = msg.role === 'assistant';
                  const isMarathiText = /[\u0900-\u097F]/.test(msg.text);

                  return (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      }}
                    >
                      <div
                        className={`chat-bubble-content ${msg.role === 'user' ? 'user-bubble' : 'ai-bubble'}`}
                      >
                        {isAssistant && (
                          <div className="ai-meta-bar">
                            <span className="ai-rag-badge">
                              🛡️ Grounded RAG • Official Data
                            </span>

                            {/* One-click Bilingual Translation Button */}
                            <button
                              type="button"
                              className="ai-translate-btn"
                              onClick={() => handleAskAI(isMarathiText ? 'give in english' : 'give in marathi')}
                              title={isMarathiText ? 'Translate response to English' : 'Translate response to Marathi'}
                            >
                              {isMarathiText ? '🌐 View in English' : '🌐 मराठीत पाहा'}
                            </button>
                          </div>
                        )}

                        {renderFormattedContent(msg.text, msg.role === 'user')}

                        {/* Cited Sources Card list if attached */}
                        {msg.response && msg.response.sources && msg.response.sources.length > 0 && (
                          <div className="ai-sources-card">
                            <span className="ai-sources-title">
                              🏛️ {strings.aiSourcesTitle}:
                            </span>
                            <div style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                              {msg.response.sources.map((s) => (
                                <div key={s.id} className="ai-source-item">
                                  <span>🔗</span>
                                  <a href={s.source_url} target="_blank" rel="noreferrer">
                                    {lang === 'mr' && s.title_mr ? s.title_mr : s.title}
                                  </a>
                                  <span style={{ color: '#64748b', fontSize: '0.78rem' }}>({s.department})</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Factual Disclaimer */}
                        {msg.response && msg.response.disclaimer && (
                          <div className="ai-disclaimer-box">
                            <span>⚖️</span>
                            <span>{msg.response.disclaimer}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}

                {isAiLoading && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#0284c7', fontSize: '0.9rem', fontStyle: 'italic', padding: '0.5rem' }}>
                    <span className="spinner-sm" /> ⏳ {strings.aiThinking}
                  </div>
                )}
                <div ref={chatMessagesEndRef} />
              </div>

              {/* Chat Input */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAskAI();
                }}
                style={{ display: 'flex', gap: '0.5rem' }}
              >
                <input
                  type="text"
                  placeholder={strings.aiInputPlaceholder}
                  value={aiQuestion}
                  onChange={(e) => setAiQuestion(e.target.value)}
                  style={{
                    flex: 1,
                    padding: '0.85rem 1.1rem',
                    borderRadius: '10px',
                    border: '1px solid #cbd5e1',
                    outline: 'none',
                    fontSize: '0.95rem',
                  }}
                />
                <button
                  type="submit"
                  className="btn-details"
                  disabled={isAiLoading || !aiQuestion.trim()}
                  style={{ padding: '0 1.5rem', fontSize: '0.95rem' }}
                >
                  {strings.btnSend} 🚀
                </button>
              </form>
            </div>
          </section>
        )}

        {/* TAB: ABOUT & VALIDATED SOURCES REGISTRY */}
        {activeTab === 'about' && (
          <section className="about-section" style={{ margin: '2rem 0' }}>
            <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
              <div className="hero-badge" style={{ display: 'inline-block', marginBottom: '0.5rem' }}>
                🛡️ {lang === 'mr' ? 'पारदर्शकता व अधिकृत स्रोत' : 'Public Transparency & Sources'}
              </div>
              <h2 style={{ fontSize: '2rem', color: 'var(--primary-navy)', fontWeight: 700 }}>
                {strings.aboutHeading}
              </h2>
              <p style={{ color: '#64748b', marginTop: '0.5rem', maxWidth: '720px', margin: '0.5rem auto 0' }}>
                {lang === 'mr'
                  ? 'महासेवा एआय हे नागरिकांना महाराष्ट्र शासनाच्या अधिकृत योजना शोधण्यासाठी, पात्रता तपासण्यासाठी व मुदतीची अचूक माहिती मिळवण्यासाठी तयार केलेले एक स्वतंत्र नागरिक साहाय्यक व्यासपीठ आहे.'
                  : 'MahaSeva AI is an intelligent citizen-assistance discovery platform dedicated exclusively to Maharashtra State Government schemes, resolutions, and benefits.'}
              </p>
            </div>

            {/* Core Architectural Pillars */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginBottom: '3rem' }}>
              <div className="stat-card" style={{ textAlign: 'left', padding: '1.5rem' }}>
                <div style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>🏛️</div>
                <h4 style={{ color: 'var(--primary-navy)', fontWeight: 700, marginBottom: '0.5rem' }}>
                  {lang === 'mr' ? '१००% महाराष्ट्र शासन केंद्रित' : '100% Maharashtra Focused'}
                </h4>
                <p style={{ color: '#64748b', fontSize: '0.88rem', lineHeight: 1.5 }}>
                  {lang === 'mr'
                    ? 'केवळ महाराष्ट्र शासन संकेतस्थळे, विभाग, जिल्हाधिकारी कार्यालये व अधिकृत शासकीय पोर्टलवरूनच माहिती संकलित केली जाते. कोणतेही त्रयस्थ किंवा असंबद्ध स्रोत वापरले जात नाहीत.'
                    : 'Restricted strictly to official Maharashtra departments, collectorates, scholarship portals, and state gazettes. No unrelated or unverified national aggregators.'}
                </p>
              </div>

              <div className="stat-card" style={{ textAlign: 'left', padding: '1.5rem' }}>
                <div style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>🎯</div>
                <h4 style={{ color: 'var(--primary-navy)', fontWeight: 700, marginBottom: '0.5rem' }}>
                  {lang === 'mr' ? 'सत्यता पडताळणी व RAG' : 'Grounded Hybrid RAG'}
                </h4>
                <p style={{ color: '#64748b', fontSize: '0.88rem', lineHeight: 1.5 }}>
                  {lang === 'mr'
                    ? 'एआय स्वतःहून कोणतीही खोटी तारीख, अनुदान रक्कम किंवा कागदपत्रे तयार करत नाही. उपलब्ध शासकीय पुराव्यावरूनच उत्तर दिले जाते; मुदत नसल्यास तसे स्पष्ट नमूद केले जाते.'
                    : 'The AI answers are grounded in verified database records and official Government Resolutions. If a deadline has not been published, the system explicitly reports that.'}
                </p>
              </div>

              <div className="stat-card" style={{ textAlign: 'left', padding: '1.5rem' }}>
                <div style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>🔒</div>
                <h4 style={{ color: 'var(--primary-navy)', fontWeight: 700, marginBottom: '0.5rem' }}>
                  {lang === 'mr' ? 'गोपनीयतेची १००% हमी' : 'Zero Data Retention'}
                </h4>
                <p style={{ color: '#64748b', fontSize: '0.88rem', lineHeight: 1.5 }}>
                  {lang === 'mr'
                    ? 'नागरिकांचा कोणताही आधार क्रमांक, बँक खाते, पासवर्ड किंवा फोन नंबर मागितला अथवा साठवला जात नाही. सत्र संपल्यावर किंवा रिफ्रेश केल्यावर संवाद नष्ट होतो.'
                    : 'No Aadhaar numbers, OTPs, or bank details are ever requested or stored. Chat sessions are strictly temporary and are cleared upon page refresh or closing.'}
                </p>
              </div>
            </div>

            {/* Official Sources Registry Table */}
            <div style={{ background: '#ffffff', borderRadius: '16px', border: '1px solid #cbd5e1', padding: '2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div>
                  <h3 style={{ fontSize: '1.3rem', color: 'var(--primary-navy)', fontWeight: 700 }}>
                    📋 {strings.officialSourcesTitle}
                  </h3>
                  <p style={{ color: '#64748b', fontSize: '0.88rem', marginTop: '0.25rem' }}>
                    {strings.officialSourcesDesc} ({publicSources.length > 0 ? publicSources.length : 58} {lang === 'mr' ? 'पडताळणी झालेले अधिकृत स्रोत' : 'validated official portals'})
                  </p>
                </div>
                <span className="badge badge-verified" style={{ padding: '0.5rem 0.9rem', fontSize: '0.85rem' }}>
                  ✓ Official .gov.in & .nic.in Only
                </span>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table className="admin-changes-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>{lang === 'mr' ? 'अधिकृत पोर्टल / विभागाचे नाव' : 'Portal / Department Name'}</th>
                      <th>{lang === 'mr' ? 'वर्गवारी' : 'Category'}</th>
                      <th>{lang === 'mr' ? 'स्थिती' : 'Status'}</th>
                      <th>{lang === 'mr' ? 'अधिकृत लिंक' : 'Official Portal Link'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(publicSources.length > 0 ? publicSources : sourcesList).map((src, idx) => (
                      <tr key={src.id || idx}>
                        <td>{idx + 1}</td>
                        <td>
                          <strong>{src.name}</strong>
                          <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{src.department || src.name}</div>
                        </td>
                        <td>
                          <span className="badge" style={{ background: '#f1f5f9', color: '#334155' }}>
                            {src.source_category || 'State Portal'}
                          </span>
                        </td>
                        <td>
                          <span style={{ color: '#059669', fontWeight: 600, fontSize: '0.82rem' }}>
                            ✓ {src.verification_status || 'Verified Official'}
                          </span>
                        </td>
                        <td>
                          <a
                            href={src.url || (src.start_urls && src.start_urls[0]) || '#'}
                            target="_blank"
                            rel="noreferrer"
                            style={{ color: '#2563eb', textDecoration: 'underline', fontSize: '0.84rem' }}
                          >
                            🔗 {src.url || (src.start_urls && src.start_urls[0]) || 'Official Portal'}
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* TAB 4: OFFICER / ADMIN PORTAL */}
        {activeTab === 'admin' && (
          <section style={{ margin: '2rem 0' }}>
            {!adminToken ? (
              <div style={{ maxWidth: '420px', margin: '3rem auto' }} className="stat-card">
                <h3 style={{ color: 'var(--primary-navy)', marginBottom: '1rem', fontSize: '1.4rem' }}>
                  🔒 {strings.navAdmin}
                </h3>
                {adminLoginError && (
                  <div style={{ color: '#b91c1c', marginBottom: '1rem', fontSize: '0.85rem' }}>
                    ⚠️ {adminLoginError}
                  </div>
                )}
                <form onSubmit={handleAdminLogin} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                  <input
                    type="text"
                    placeholder="Username"
                    value={adminUsernameInput}
                    onChange={(e) => setAdminUsernameInput(e.target.value)}
                    style={{ padding: '0.75rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    required
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={adminPasswordInput}
                    onChange={(e) => setAdminPasswordInput(e.target.value)}
                    style={{ padding: '0.75rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    required
                  />
                  <button type="submit" className="btn-details" style={{ justifyContent: 'center' }}>
                    Sign In
                  </button>
                </form>
              </div>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <div>
                    <h3 style={{ fontSize: '1.6rem', color: 'var(--primary-navy)' }}>
                      🛡️ Officer Verification Dashboard
                    </h3>
                    <p style={{ color: '#64748b' }}>Logged in as {adminUser?.username} ({adminUser?.role})</p>
                  </div>
                  <button className="btn-details" onClick={handleAdminLogout} style={{ background: '#64748b' }}>
                    Log Out
                  </button>
                </div>

                {/* Live Monitoring Scheduler Status Banner */}
                <div className="scheduler-status-banner">
                  <div className="scheduler-meta-left">
                    <h4>⚡ {strings.adminSchedulerLive}</h4>
                    <p>
                      Automated crawler & deadline recalculator: {schedulerStatus?.is_alive ? 'Online & Monitoring' : 'Active'}. Last check: {schedulerStatus?.last_run_finished_at ? schedulerStatus.last_run_finished_at.slice(0, 16) : 'Recently completed'}.
                    </p>
                  </div>
                  <div>
                    <button className="btn-details" onClick={handleTriggerScan} style={{ background: '#f59e0b' }}>
                      🔄 {strings.adminRunScanBtn}
                    </button>
                  </div>
                </div>

                {syncStatusMsg && (
                  <div style={{ padding: '0.75rem 1rem', background: '#ecfdf5', color: '#047857', borderRadius: '8px', marginBottom: '1rem' }}>
                    {syncStatusMsg}
                  </div>
                )}

                {/* Admin Subtabs */}
                <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '2px solid #e2e8f0', marginBottom: '1.5rem' }}>
                  <button
                    className={`status-tab ${adminViewTab === 'review' ? 'active' : ''}`}
                    onClick={() => setAdminViewTab('review')}
                  >
                    {strings.adminTabReview}
                  </button>
                  <button
                    className={`status-tab ${adminViewTab === 'changes' ? 'active' : ''}`}
                    onClick={() => setAdminViewTab('changes')}
                  >
                    {strings.adminTabChanges} ({changesList.length})
                  </button>
                  <button
                    className={`status-tab ${adminViewTab === 'audit' ? 'active' : ''}`}
                    onClick={() => setAdminViewTab('audit')}
                  >
                    {strings.adminTabAudit}
                  </button>
                  <button
                    className={`status-tab ${adminViewTab === 'sources' ? 'active' : ''}`}
                    onClick={() => setAdminViewTab('sources')}
                  >
                    {strings.adminTabSources}
                  </button>
                </div>

                {/* Subtab 1: Candidate Review Queue */}
                {adminViewTab === 'review' && (
                  <div>
                    <p style={{ color: '#64748b', marginBottom: '1rem' }}>
                      Review candidates discovered by the monitoring scraper. Verify eligibility, deadlines, and official links.
                    </p>
                    <div className="schemes-grid">
                      {schemes.slice(0, 8).map((scheme) => (
                        <div key={scheme.id} className="scheme-card">
                          <div>
                            <span className="badge badge-dept">{scheme.department}</span>
                            <h4 style={{ fontSize: '1rem', marginTop: '0.5rem', fontWeight: 700 }}>
                              {scheme.title}
                            </h4>
                            <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '0.5rem 0' }}>
                              Status: <strong>{scheme.verification_status}</strong> | Window: <strong>{scheme.current_window_status}</strong>
                            </p>
                          </div>
                          <button
                            className="btn-details"
                            onClick={() => openReviewModal(scheme)}
                            style={{ marginTop: '1rem', justifyContent: 'center' }}
                          >
                            Review & Verify →
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Subtab 2: Detected Changes Queue */}
                {adminViewTab === 'changes' && (
                  <div>
                    <p style={{ color: '#64748b', marginBottom: '1rem' }}>
                      Official notifications, deadline extensions, and content modifications detected by the automated monitoring system.
                    </p>
                    {changesList.length === 0 ? (
                      <p style={{ padding: '2rem', textAlign: 'center', background: '#fff', borderRadius: '8px' }}>
                        No pending changes detected.
                      </p>
                    ) : (
                      <table className="admin-changes-table">
                        <thead>
                          <tr>
                            <th>ID</th>
                            <th>Scheme ID</th>
                            <th>Change Type</th>
                            <th>Field</th>
                            <th>Previous Value</th>
                            <th>New Value</th>
                            <th>Detected At</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {changesList.map((chg) => (
                            <tr key={chg.id}>
                              <td>#{chg.id}</td>
                              <td>{chg.scheme_id ? `#${chg.scheme_id}` : 'New Candidate'}</td>
                              <td>
                                <span className="status-badge status-closing-soon">
                                  {chg.change_type}
                                </span>
                              </td>
                              <td>{chg.field_name || '-'}</td>
                              <td style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {chg.previous_value || '-'}
                              </td>
                              <td style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 600 }}>
                                {chg.new_value || '-'}
                              </td>
                              <td>{chg.detection_timestamp.slice(0, 16)}</td>
                              <td>
                                {chg.review_status === 'pending_review' ? (
                                  <>
                                    <button
                                      className="btn-approve-sm"
                                      onClick={() => handleReviewChange(chg.id, 'approved')}
                                    >
                                      ✓ Approve
                                    </button>
                                    <button
                                      className="btn-reject-sm"
                                      onClick={() => handleReviewChange(chg.id, 'rejected')}
                                    >
                                      ✕ Reject
                                    </button>
                                  </>
                                ) : (
                                  <span style={{ fontWeight: 600, color: chg.review_status === 'approved' ? '#059669' : '#dc2626' }}>
                                    {chg.review_status}
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}

                {/* Subtab 3: Verification Audits */}
                {adminViewTab === 'audit' && (
                  <div>
                    <table className="admin-changes-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Candidate ID</th>
                          <th>Officer</th>
                          <th>Action</th>
                          <th>Previous</th>
                          <th>New Status</th>
                          <th>Timestamp</th>
                        </tr>
                      </thead>
                      <tbody>
                        {auditLogs.map((log) => (
                          <tr key={log.id}>
                            <td>#{log.id}</td>
                            <td>#{log.candidate_id}</td>
                            <td><strong>{log.reviewer_username}</strong></td>
                            <td>{log.action}</td>
                            <td>{log.previous_status}</td>
                            <td><strong>{log.new_status}</strong></td>
                            <td>{log.created_at.slice(0, 16)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Subtab 4: Source Registry */}
                {adminViewTab === 'sources' && (
                  <div>
                    <table className="admin-changes-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Portal Name</th>
                          <th>Department</th>
                          <th>Category</th>
                          <th>Priority</th>
                          <th>Interval</th>
                          <th>Last Checked</th>
                          <th>Health</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sourcesList.map((src) => (
                          <tr key={src.id}>
                            <td>#{src.id}</td>
                            <td><strong>{src.name}</strong></td>
                            <td>{src.department || src.name}</td>
                            <td>{src.source_category || 'Portal'}</td>
                            <td>
                              <span className="badge" style={{ background: '#f1f5f9' }}>
                                {src.priority || 'medium'}
                              </span>
                            </td>
                            <td>{src.monitoring_frequency_hours || 24}h</td>
                            <td>{src.last_crawled_at ? src.last_crawled_at.slice(0, 16) : 'Scheduled'}</td>
                            <td>
                              <span style={{ color: '#059669', fontWeight: 600 }}>● Active</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {collectionRuns.length > 0 && (
                      <div style={{ marginTop: '2.5rem' }}>
                        <h4 style={{ color: 'var(--primary-navy)', marginBottom: '0.75rem', fontWeight: 700 }}>
                          Recent Monitoring Crawl Passes
                        </h4>
                        <table className="admin-changes-table">
                          <thead>
                            <tr>
                              <th>Run ID</th>
                              <th>Started At</th>
                              <th>Status</th>
                              <th>Evaluated</th>
                              <th>New Discovered</th>
                              <th>Updated</th>
                            </tr>
                          </thead>
                          <tbody>
                            {collectionRuns.slice(0, 5).map((r) => (
                              <tr key={r.id}>
                                <td>#{r.id}</td>
                                <td>{r.started_at.slice(0, 16)}</td>
                                <td><span className="badge badge-verified">{r.status}</span></td>
                                <td>{r.total_candidates}</td>
                                <td><strong>+{r.new_candidates}</strong></td>
                                <td>{r.updated_candidates}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        )}
      </main>

      {/* Scheme Detail Modal */}
      {selectedSchemeId && (isLoadingDetail ? (
        <div className="chat-modal-backdrop" onClick={() => setSelectedSchemeId(null)}>
          <div className="chat-modal-dialog" style={{ maxHeight: '200px', maxWidth: '400px', padding: '2rem', textAlign: 'center', justifyContent: 'center', alignItems: 'center' }}>
            <p style={{ color: 'var(--primary-navy)', fontWeight: 600 }}>Loading scheme details...</p>
          </div>
        </div>
      ) : schemeDetail && (
        <div
          className="chat-modal-backdrop"
          onClick={() => {
            setSelectedSchemeId(null);
            setSchemeDetail(null);
          }}
        >
          <div
            className="chat-modal-dialog"
            style={{ maxHeight: '85vh', maxWidth: '780px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="chat-modal-header">
              <div className="chat-modal-scheme-meta">
                <h4>{lang === 'mr' && schemeDetail.title_mr ? schemeDetail.title_mr : schemeDetail.title}</h4>
                <p>🏛️ {schemeDetail.department} | {schemeDetail.category}</p>
              </div>
              <button
                onClick={() => {
                  setSelectedSchemeId(null);
                  setSchemeDetail(null);
                }}
                style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '1.25rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <div className="chat-modal-body" style={{ background: '#fff' }}>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                <span className={`status-badge ${schemeDetail.badge_class || 'status-open'}`}>
                  ● {lang === 'mr' && schemeDetail.status_label_mr ? schemeDetail.status_label_mr : schemeDetail.status_label_en}
                </span>
                <span className="badge badge-dept">{schemeDetail.verification_status}</span>
              </div>

              {/* Deadline notice */}
              <div className="card-date-meta" style={{ marginBottom: '1.25rem' }}>
                {schemeDetail.current_window_status === 'no_deadline_published' ? (
                  <span>ℹ️ {strings.noDeadlineNotice}</span>
                ) : (
                  <span>📅 <strong>{strings.cardDeadline}:</strong> {schemeDetail.application_deadline || 'Open'}</span>
                )}
              </div>

              {/* Application Windows History table if rounds exist */}
              {schemeDetail.application_windows && schemeDetail.application_windows.length > 0 && (
                <div style={{ marginBottom: '1.5rem', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '0.75rem' }}>
                  <h5 style={{ color: 'var(--primary-navy)', marginBottom: '0.5rem', fontWeight: 700 }}>
                    🗓️ {strings.detailWindowsTitle}
                  </h5>
                  <table style={{ width: '100%', fontSize: '0.82rem', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ background: '#f8fafc', textAlign: 'left' }}>
                        <th style={{ padding: '4px' }}>Round</th>
                        <th style={{ padding: '4px' }}>Start Date</th>
                        <th style={{ padding: '4px' }}>Deadline</th>
                        <th style={{ padding: '4px' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {schemeDetail.application_windows.map((w) => (
                        <tr key={w.id} style={{ borderTop: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '4px' }}>{w.window_name}</td>
                          <td style={{ padding: '4px' }}>{w.start_date || '-'}</td>
                          <td style={{ padding: '4px' }}>{w.deadline_date || '-'}</td>
                          <td style={{ padding: '4px' }}>
                            <span className="status-badge" style={{ fontSize: '0.7rem' }}>
                              {w.window_status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <h5 style={{ color: 'var(--primary-navy)', fontWeight: 700 }}>{strings.cardBenefits}</h5>
              <p style={{ color: '#475569', fontSize: '0.92rem', marginBottom: '1rem' }}>
                {schemeDetail.benefits || schemeDetail.brief_description || 'Detailed benefits specified in Government Resolution.'}
              </p>

              <h5 style={{ color: 'var(--primary-navy)', fontWeight: 700 }}>{strings.cardEligibility}</h5>
              <p style={{ color: '#475569', fontSize: '0.92rem', marginBottom: '1rem' }}>
                {schemeDetail.eligibility || 'Subject to departmental criteria and residence requirements.'}
              </p>

              <h5 style={{ color: 'var(--primary-navy)', fontWeight: 700 }}>{strings.detailDocsRequired}</h5>
              <p style={{ color: '#475569', fontSize: '0.92rem', marginBottom: '1rem' }}>
                {schemeDetail.documents_required || 'Aadhaar card, residence proof, income certificate, bank passbook.'}
              </p>

              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid #e2e8f0' }}>
                {schemeDetail.official_apply_url && (
                  <a href={schemeDetail.official_apply_url} target="_blank" rel="noreferrer" className="btn-details">
                    🚀 {strings.btnApplyNow}
                  </a>
                )}
                <a href={schemeDetail.source_url} target="_blank" rel="noreferrer" className="official-link-icon">
                  🔗 {strings.btnOfficialLink}
                </a>
                <button
                  className="btn-ask-scheme"
                  onClick={() => {
                    handleOpenContextualChat(schemeDetail);
                    setSelectedSchemeId(null);
                  }}
                >
                  💬 {strings.btnAskAboutScheme}
                </button>
              </div>
            </div>
          </div>
        </div>
      ))}

      {/* Contextual Temporary Chat Modal */}
      {contextualScheme && (
        <div className="chat-modal-backdrop" onClick={handleCloseContextualChat}>
          <div className="chat-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="chat-modal-header">
              <div className="chat-modal-scheme-meta">
                <h4>💬 {strings.chatModalTitle}</h4>
                <p>
                  {lang === 'mr' && contextualScheme.title_mr ? contextualScheme.title_mr : contextualScheme.title} (
                  {contextualScheme.department})
                </p>
              </div>
              <button
                onClick={handleCloseContextualChat}
                style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '1.25rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <div className="chat-modal-body">
              {contextualMessages.map((m, idx) => (
                <div key={idx} className={`chat-bubble-row ${m.role === 'user' ? 'user-row' : ''}`}>
                  <div className={`chat-bubble-content ${m.role === 'user' ? 'user-bubble' : 'ai-bubble'}`}>
                    {renderFormattedContent(m.text, m.role === 'user')}
                  </div>
                </div>
              ))}
              {isContextualLoading && (
                <div style={{ color: '#64748b', fontStyle: 'italic', fontSize: '0.85rem' }}>
                  ⏳ {strings.aiThinking}
                </div>
              )}
              <div ref={contextualMessagesEndRef} />
            </div>

            <div className="chat-modal-footer">
              <div className="chat-quick-chips">
                <button
                  type="button"
                  className="chip-btn"
                  disabled={isContextualLoading}
                  onClick={() => handleSendContextualText(strings.chipEligibility)}
                >
                  {strings.chipEligibility}
                </button>
                <button
                  type="button"
                  className="chip-btn"
                  disabled={isContextualLoading}
                  onClick={() => handleSendContextualText(strings.chipDocuments)}
                >
                  {strings.chipDocuments}
                </button>
                <button
                  type="button"
                  className="chip-btn"
                  disabled={isContextualLoading}
                  onClick={() => handleSendContextualText(strings.chipHowToApply)}
                >
                  {strings.chipHowToApply}
                </button>
                <button
                  type="button"
                  className="chip-btn"
                  disabled={isContextualLoading}
                  onClick={() => handleSendContextualText(strings.chipDeadline)}
                >
                  {strings.chipDeadline}
                </button>
              </div>

              <form onSubmit={handleSendContextualQuery} className="chat-input-bar">
                <input
                  type="text"
                  placeholder={strings.chatModalInput}
                  value={contextualInput}
                  onChange={(e) => setContextualInput(e.target.value)}
                  autoFocus
                />
                <button type="submit" disabled={isContextualLoading || !contextualInput.trim()}>
                  {strings.btnSend}
                </button>
              </form>
              <div className="chat-privacy-hint">
                🔒 {strings.chatNoticeNoPersist}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Admin Review Modal */}
      {reviewingScheme && (
        <div className="chat-modal-backdrop" onClick={() => setReviewingScheme(null)}>
          <div className="chat-modal-dialog" style={{ maxHeight: '90vh' }} onClick={(e) => e.stopPropagation()}>
            <div className="chat-modal-header">
              <h4>Review Candidate #{reviewingScheme.id}: {reviewingScheme.title}</h4>
              <button onClick={() => setReviewingScheme(null)} style={{ background: 'transparent', border: 'none', color: '#fff' }}>✕</button>
            </div>
            <form onSubmit={handleSaveReview} className="chat-modal-body" style={{ background: '#fff' }}>
              <label style={{ fontWeight: 600 }}>Verification Decision:</label>
              <select
                value={reviewStatus}
                onChange={(e) => setReviewStatus(e.target.value)}
                style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}
              >
                <option value="verified">Verified State Scheme</option>
                <option value="pending_review">Pending Review</option>
                <option value="needs_update">Needs Update</option>
                <option value="rejected">Rejected</option>
                <option value="outdated">Outdated</option>
              </select>

              <label style={{ fontWeight: 600, marginTop: '0.5rem' }}>Category:</label>
              <input
                type="text"
                value={reviewCategory}
                onChange={(e) => setReviewCategory(e.target.value)}
                style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}
              />

              <label style={{ fontWeight: 600, marginTop: '0.5rem' }}>Application Deadline (YYYY-MM-DD):</label>
              <input
                type="text"
                value={reviewDeadline}
                onChange={(e) => setReviewDeadline(e.target.value)}
                placeholder="e.g. 2026-12-31 (Leave blank if no published deadline)"
                style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}
              />

              <label style={{ fontWeight: 600, marginTop: '0.5rem' }}>Official Apply URL:</label>
              <input
                type="text"
                value={reviewApplyUrl}
                onChange={(e) => setReviewApplyUrl(e.target.value)}
                style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}
              />

              <label style={{ fontWeight: 600, marginTop: '0.5rem' }}>Reviewer Notes:</label>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Rationale for decision (recorded in immutable audit log)"
                rows={3}
                style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}
              />

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
                <button type="button" onClick={() => setReviewingScheme(null)} className="btn-details" style={{ background: '#94a3b8' }}>
                  Cancel
                </button>
                <button type="submit" className="btn-details" disabled={isSubmittingReview}>
                  {isSubmittingReview ? 'Saving...' : 'Save & Publish Decision'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer style={{ background: 'var(--primary-navy)', color: '#94a3b8', padding: '3.5rem 0', borderTop: '1px solid #1e293b' }}>
        <div className="container" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '1.3rem', color: '#fff', fontWeight: 700, marginBottom: '0.6rem' }}>
            🏛️ {strings.siteTitle}
          </div>
          <p style={{ maxWidth: '720px', margin: '0 auto 1.5rem', fontSize: '0.85rem', lineHeight: 1.6, color: '#94a3b8' }}>
            {strings.footerDisclaimer}
          </p>

          <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: '1.25rem', marginBottom: '1.5rem', fontSize: '0.86rem' }}>
            <a
              href="https://www.maharashtra.gov.in/"
              target="_blank"
              rel="noreferrer"
              style={{ color: '#93c5fd', textDecoration: 'underline' }}
            >
              🏛️ Maharashtra State Portal
            </a>
            <a
              href="https://ladakibahin.maharashtra.gov.in/"
              target="_blank"
              rel="noreferrer"
              style={{ color: '#93c5fd', textDecoration: 'underline' }}
            >
              🌸 Mukhyamantri Majhi Ladki Bahin
            </a>
            <a
              href="https://mahadbt.maharashtra.gov.in/"
              target="_blank"
              rel="noreferrer"
              style={{ color: '#93c5fd', textDecoration: 'underline' }}
            >
              🎓 MahaDBT Portal
            </a>
            <a
              href="https://aaplesarkar.mahaonline.gov.in/"
              target="_blank"
              rel="noreferrer"
              style={{ color: '#93c5fd', textDecoration: 'underline' }}
            >
              📋 Aaple Sarkar Citizen Services
            </a>
            <a
              href="https://gr.maharashtra.gov.in/"
              target="_blank"
              rel="noreferrer"
              style={{ color: '#93c5fd', textDecoration: 'underline' }}
            >
              📜 Maharashtra Government Resolutions (GR)
            </a>
          </div>

          <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
            🔒 {strings.footerPrivacy}
          </div>
        </div>
      </footer>
    </div>
  );
}
