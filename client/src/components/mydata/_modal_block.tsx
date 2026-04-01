// ── Add data modal ────────────────────────────────────────────────────────────
// Flow: category (mandatory) → method → form
function AddDataModal({ open, onClose, isDark, theme }: {
  open: boolean; onClose: () => void; isDark: boolean; theme: Theme;
}) {
  type Step = 'category' | 'method' | 'csv' | 'manual' | 'sheets' | 'api';
  const [step, setStep] = useState<Step>('category');
  const [selectedCategory, setSelectedCategory] = useState<DataCategory | null>(null);
  const [expandedGuide, setExpandedGuide] = useState<DataCategory | null>(null);

  const allCategories = Object.keys(CATEGORY_CONFIG) as DataCategory[];

  const methods = [
    { id: 'csv' as const,    icon: UploadFileRoundedIcon, label: 'Upload CSV / Excel', desc: 'Import rows from a file',       color: '#34d399' },
    { id: 'manual' as const, icon: EditRoundedIcon,       label: 'Manual Entry',       desc: 'Type data fields directly',    color: '#c084fc' },
    { id: 'sheets' as const, icon: TableChartRoundedIcon, label: 'Google Sheets',      desc: 'Sync live from a spreadsheet', color: '#60a5fa' },
    { id: 'api' as const,    icon: ApiRoundedIcon,        label: 'API / Webhook',      desc: 'Connect via REST endpoint',    color: '#22d3ee' },
  ];

  const inputSx = {
    px: 1.25, py: 0.85, borderRadius: '9px', fontSize: '0.8rem',
    color: 'text.primary', flex: 1,
    background: isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03),
    border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
    '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 },
    '&:focus-within': { borderColor: isDark ? 'rgba(129,140,248,0.5)' : alpha(theme.palette.primary.main, 0.5) },
    transition: 'border-color 0.15s ease',
  };

  const handleClose = () => {
    onClose();
    setStep('category');
    setSelectedCategory(null);
    setExpandedGuide(null);
  };

  const handleBack = () => {
    if (step === 'method') { setStep('category'); setSelectedCategory(null); }
    else if (['csv', 'manual', 'sheets', 'api'].includes(step)) setStep('method');
  };

  const headerTitle: Record<Step, string> = {
    category: 'Add Business Data',
    method:   'How do you want to add data?',
    csv:      'Upload CSV / Excel',
    manual:   'Manual Entry',
    sheets:   'Connect Google Sheets',
    api:      'API / Webhook',
  };

  return (
    <Modal open={open} onClose={handleClose} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 1.5, sm: 2 } }}>
      <Box sx={{
        width: '100%',
        maxWidth: 480,
        maxHeight: '90vh',
        borderRadius: '18px',
        background: isDark ? '#0f172a' : '#fff',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
        boxShadow: isDark ? '0 32px 80px rgba(0,0,0,0.7)' : '0 32px 80px rgba(15,23,42,0.18)',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
        animation: 'modalIn 0.2s ease-out',
        '@keyframes modalIn': { from: { opacity: 0, transform: 'scale(0.97) translateY(6px)' }, to: { opacity: 1, transform: 'scale(1) translateY(0)' } },
      }}>

        {/* Header */}
        <Box sx={{
          px: 2.25, pt: 2, pb: 1.5, flexShrink: 0,
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1,
        }}>
          <Box>
            <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
              {headerTitle[step]}
            </Typography>
            <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', mt: 0.3, lineHeight: 1.4 }}>
              {step === 'category'
                ? 'Choose a category — required before adding any data'
                : selectedCategory
                  ? `${CATEGORY_CONFIG[selectedCategory].emoji} ${CATEGORY_CONFIG[selectedCategory].label}`
                  : 'Fill in the details below'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5, flexShrink: 0 }}>
            {step !== 'category' && (
              <IconButton size="small" onClick={handleBack} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', transition: 'background 0.15s ease', '&:hover': { background: isDark ? 'rgba(255,255,255,0.08)' : alpha(theme.palette.text.primary, 0.06) } }}>
                <ExpandMoreRoundedIcon sx={{ fontSize: 16, transform: 'rotate(90deg)' }} />
              </IconButton>
            )}
            <IconButton size="small" onClick={handleClose} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', transition: 'background 0.15s ease', '&:hover': { background: isDark ? 'rgba(255,255,255,0.08)' : alpha(theme.palette.text.primary, 0.06) } }}>
              <CloseRoundedIcon sx={{ fontSize: 15 }} />
            </IconButton>
          </Box>
        </Box>

        {/* Scrollable body */}
        <Box sx={{
          flex: 1, overflowY: 'auto', minHeight: 0,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
        }}>

          {/* Step: Category selection */}
          {step === 'category' && (
            <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
                <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  Required — select one
                </Typography>
              </Box>

              {allCategories.map(cat => {
                const cfg = CATEGORY_CONFIG[cat];
                const Icon = CATEGORY_ICONS[cat];
                const isSelected = selectedCategory === cat;
                const isExpanded = expandedGuide === cat;
                return (
                  <Box key={cat}>
                    <Box
                      component="button"
                      onClick={() => { setSelectedCategory(cat); setExpandedGuide(isExpanded ? null : cat); }}
                      sx={{
                        width: '100%', display: 'flex', alignItems: 'center', gap: 1.25,
                        px: 1.25, py: 0.9, borderRadius: '10px',
                        cursor: 'pointer', textAlign: 'left',
                        background: isSelected
                          ? isDark ? alpha(cfg.color, 0.15) : alpha(cfg.color, 0.08)
                          : 'transparent',
                        border: `1.5px solid ${isSelected ? alpha(cfg.color, 0.6) : isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
                        transition: 'all 0.18s ease',
                        '&:hover': {
                          background: isDark ? alpha(cfg.color, 0.1) : alpha(cfg.color, 0.06),
                          borderColor: alpha(cfg.color, 0.5),
                          transform: 'translateX(2px)',
                        },
                        '&:active': { transform: 'scale(0.99)' },
                      }}
                    >
                      <Box sx={{
                        width: 32, height: 32, borderRadius: '9px', flexShrink: 0,
                        background: alpha(cfg.color, isDark ? 0.2 : 0.12),
                        border: `1px solid ${alpha(cfg.color, 0.25)}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        <Icon sx={{ fontSize: 15, color: cfg.color }} />
                      </Box>
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography sx={{ fontSize: '0.78rem', fontWeight: isSelected ? 700 : 600, color: isSelected ? cfg.color : 'text.primary', lineHeight: 1.3 }}>
                          {cfg.emoji} {cfg.label}
                        </Typography>
                        <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.1, lineHeight: 1.3 }}>
                          {cfg.description}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
                        {isSelected && <CheckCircleRoundedIcon sx={{ fontSize: 15, color: cfg.color }} />}
                        <Tooltip title={isExpanded ? 'Hide guide' : 'Show guide'} placement="top">
                          <Box
                            component="span"
                            onClick={e => { e.stopPropagation(); setExpandedGuide(isExpanded ? null : cat); }}
                            sx={{
                              width: 20, height: 20, borderRadius: '50%',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              background: isExpanded ? alpha(cfg.color, 0.2) : isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.05),
                              color: isExpanded ? cfg.color : 'text.disabled',
                              transition: 'all 0.15s ease',
                              '&:hover': { background: alpha(cfg.color, 0.2), color: cfg.color },
                            }}
                          >
                            <InfoOutlinedIcon sx={{ fontSize: 12 }} />
                          </Box>
                        </Tooltip>
                      </Box>
                    </Box>

                    {isExpanded && (
                      <Box sx={{
                        mx: 0.5, mt: 0.25, mb: 0.25, px: 1.5, py: 1.25,
                        borderRadius: '10px',
                        background: isDark ? alpha(cfg.color, 0.07) : alpha(cfg.color, 0.04),
                        border: `1px solid ${alpha(cfg.color, isDark ? 0.2 : 0.15)}`,
                        animation: 'guideIn 0.18s ease-out',
                        '@keyframes guideIn': { from: { opacity: 0, transform: 'translateY(-4px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
                      }}>
                        <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary', lineHeight: 1.6, mb: 1 }}>
                          {cfg.guide}
                        </Typography>
                        <Typography sx={{ fontSize: '0.57rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 0.5 }}>
                          Example columns
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.4, mb: 0.9 }}>
                          {cfg.exampleColumns.map(col => (
                            <Box key={col} sx={{
                              px: 0.65, py: 0.2, borderRadius: '5px',
                              background: isDark ? alpha(cfg.color, 0.12) : alpha(cfg.color, 0.08),
                              border: `1px solid ${alpha(cfg.color, 0.22)}`,
                            }}>
                              <Typography sx={{ fontSize: '0.57rem', fontWeight: 600, color: cfg.color }}>{col}</Typography>
                            </Box>
                          ))}
                        </Box>
                        <Typography sx={{ fontSize: '0.6rem', color: 'text.secondary', lineHeight: 1.5, fontStyle: 'italic', borderTop: `1px solid ${alpha(cfg.color, 0.15)}`, pt: 0.75 }}>
                          {cfg.exampleEntry}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                );
              })}

              <Box
                component="button"
                onClick={() => { if (selectedCategory) setStep('method'); }}
                disabled={!selectedCategory}
                sx={{
                  mt: 0.75, width: '100%', border: 'none',
                  cursor: selectedCategory ? 'pointer' : 'not-allowed',
                  py: 1, borderRadius: '10px', fontWeight: 700, fontSize: '0.8rem',
                  background: selectedCategory
                    ? `linear-gradient(135deg, ${CATEGORY_CONFIG[selectedCategory].color}, ${alpha(CATEGORY_CONFIG[selectedCategory].color, 0.75)})`
                    : isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.06),
                  color: selectedCategory ? '#fff' : theme.palette.text.disabled,
                  transition: 'all 0.2s ease',
                  boxShadow: selectedCategory ? `0 4px 16px ${alpha(CATEGORY_CONFIG[selectedCategory!].color, 0.35)}` : 'none',
                  '&:hover': { opacity: selectedCategory ? 0.9 : 1, transform: selectedCategory ? 'translateY(-1px)' : 'none' },
                  '&:active': { transform: 'scale(0.99)' },
                }}
              >
                {selectedCategory
                  ? `Continue with ${CATEGORY_CONFIG[selectedCategory].emoji} ${CATEGORY_CONFIG[selectedCategory].label}`
                  : 'Select a category to continue'}
              </Box>
            </Box>
          )}

          {/* Step: Method selection */}
          {step === 'method' && (
            <Box sx={{ p: 2, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
              {methods.map(m => (
                <Box key={m.id} component="button" onClick={() => setStep(m.id)} sx={{
                  display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0.75,
                  p: 1.5, borderRadius: '12px', cursor: 'pointer', textAlign: 'left',
                  background: isDark ? alpha(m.color, 0.07) : alpha(m.color, 0.05),
                  border: `1.5px solid ${alpha(m.color, isDark ? 0.18 : 0.13)}`,
                  transition: 'all 0.18s ease',
                  '&:hover': {
                    background: isDark ? alpha(m.color, 0.13) : alpha(m.color, 0.09),
                    borderColor: alpha(m.color, 0.55),
                    transform: 'translateY(-2px)',
                    boxShadow: isDark ? '0 6px 20px rgba(0,0,0,0.3)' : `0 6px 20px ${alpha(m.color, 0.15)}`,
                  },
                  '&:active': { transform: 'scale(0.98)' },
                }}>
                  <Box sx={{ width: 34, height: 34, borderRadius: '9px', background: alpha(m.color, 0.15), border: `1px solid ${alpha(m.color, 0.25)}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <m.icon sx={{ fontSize: 17, color: m.color }} />
                  </Box>
                  <Box>
                    <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.3 }}>{m.label}</Typography>
                    <Typography sx={{ fontSize: '0.62rem', color: 'text.secondary', mt: 0.2, lineHeight: 1.4 }}>{m.desc}</Typography>
                  </Box>
                </Box>
              ))}
            </Box>
          )}

          {/* Step: CSV upload */}
          {step === 'csv' && selectedCategory && (
            <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <CategoryBadge cat={selectedCategory} isDark={isDark} theme={theme} />
              <Box sx={{
                border: `2px dashed ${isDark ? 'rgba(52,211,153,0.3)' : 'rgba(52,211,153,0.4)'}`,
                borderRadius: '12px', p: 3, textAlign: 'center', cursor: 'pointer',
                background: isDark ? 'rgba(52,211,153,0.05)' : 'rgba(52,211,153,0.03)',
                transition: 'all 0.18s ease',
                '&:hover': { background: isDark ? 'rgba(52,211,153,0.09)' : 'rgba(52,211,153,0.06)', borderColor: '#34d399' },
              }}>
                <UploadFileRoundedIcon sx={{ fontSize: 30, color: '#34d399', mb: 0.75 }} />
                <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', mb: 0.3 }}>Drop CSV or Excel file here</Typography>
                <Typography sx={{ fontSize: '0.67rem', color: 'text.secondary' }}>or click to browse · Max 10 MB</Typography>
              </Box>
              <Box sx={{ px: 1.25, py: 0.9, borderRadius: '9px', background: isDark ? 'rgba(52,211,153,0.06)' : 'rgba(52,211,153,0.04)', border: `1px solid ${alpha('#34d399', 0.2)}` }}>
                <Typography sx={{ fontSize: '0.62rem', color: isDark ? '#34d399' : '#059669', fontWeight: 600, mb: 0.3 }}>Suggested columns</Typography>
                <Typography sx={{ fontSize: '0.6rem', color: 'text.secondary', lineHeight: 1.5 }}>
                  {CATEGORY_CONFIG[selectedCategory].exampleColumns.join(' · ')}
                </Typography>
              </Box>
              <Box component="button" sx={{ width: '100%', border: 'none', cursor: 'pointer', py: 0.9, borderRadius: '10px', background: 'linear-gradient(135deg, #34d399, #22d3ee)', color: '#fff', fontSize: '0.78rem', fontWeight: 700, transition: 'all 0.18s ease', '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' } }}>
                Upload & Import
              </Box>
            </Box>
          )}

          {/* Step: Manual entry */}
          {step === 'manual' && selectedCategory && (
            <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.1 }}>
              <CategoryBadge cat={selectedCategory} isDark={isDark} theme={theme} />
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Entry Title</Typography>
                <InputBase placeholder={`e.g. ${CATEGORY_CONFIG[selectedCategory].exampleColumns[0] ?? 'Entry name'}...`} sx={inputSx} fullWidth />
              </Box>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Data Content</Typography>
                <InputBase
                  placeholder={`e.g. ${CATEGORY_CONFIG[selectedCategory].exampleEntry}`}
                  multiline rows={4}
                  sx={{ ...inputSx, alignItems: 'flex-start', '& textarea': { resize: 'none' } }}
                  fullWidth
                />
              </Box>
              <Box sx={{ px: 1.25, py: 0.9, borderRadius: '9px', background: isDark ? alpha(CATEGORY_CONFIG[selectedCategory].color, 0.06) : alpha(CATEGORY_CONFIG[selectedCategory].color, 0.04), border: `1px solid ${alpha(CATEGORY_CONFIG[selectedCategory].color, 0.2)}` }}>
                <Typography sx={{ fontSize: '0.6rem', color: CATEGORY_CONFIG[selectedCategory].color, fontWeight: 600, mb: 0.25 }}>Suggested fields</Typography>
                <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', lineHeight: 1.5 }}>
                  {CATEGORY_CONFIG[selectedCategory].exampleColumns.join(' · ')}
                </Typography>
              </Box>
              <Box component="button" sx={{ width: '100%', border: 'none', cursor: 'pointer', py: 0.9, borderRadius: '10px', background: 'linear-gradient(135deg, #c084fc, #818cf8)', color: '#fff', fontSize: '0.78rem', fontWeight: 700, transition: 'all 0.18s ease', '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' } }}>
                Save Entry
              </Box>
            </Box>
          )}

          {/* Step: Google Sheets */}
          {step === 'sheets' && selectedCategory && (
            <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
              <CategoryBadge cat={selectedCategory} isDark={isDark} theme={theme} />
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Google Sheets URL</Typography>
                <InputBase placeholder="https://docs.google.com/spreadsheets/d/..." sx={inputSx} fullWidth />
              </Box>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Sheet Name (optional)</Typography>
                <InputBase placeholder="Sheet1" sx={inputSx} fullWidth />
              </Box>
              <Box sx={{ px: 1.25, py: 1, borderRadius: '9px', background: isDark ? 'rgba(96,165,250,0.07)' : 'rgba(96,165,250,0.05)', border: `1px solid ${alpha('#60a5fa', 0.2)}` }}>
                <Typography sx={{ fontSize: '0.62rem', color: isDark ? '#60a5fa' : '#0891b2', fontWeight: 600, mb: 0.25 }}>Suggested columns</Typography>
                <Typography sx={{ fontSize: '0.6rem', color: 'text.secondary', lineHeight: 1.5 }}>
                  {CATEGORY_CONFIG[selectedCategory].exampleColumns.join(' · ')}
                </Typography>
              </Box>
              <Box component="button" sx={{ width: '100%', border: 'none', cursor: 'pointer', py: 0.9, borderRadius: '10px', background: 'linear-gradient(135deg, #60a5fa, #22d3ee)', color: '#fff', fontSize: '0.78rem', fontWeight: 700, transition: 'all 0.18s ease', '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' } }}>
                Connect Sheet
              </Box>
            </Box>
          )}

          {/* Step: API / Webhook */}
          {step === 'api' && selectedCategory && (
            <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
              <CategoryBadge cat={selectedCategory} isDark={isDark} theme={theme} />
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Source Name</Typography>
                <InputBase placeholder={`e.g. ${CATEGORY_CONFIG[selectedCategory].label} API`} sx={inputSx} fullWidth />
              </Box>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Endpoint URL</Typography>
                <InputBase placeholder="https://api.yoursource.com/data" sx={inputSx} fullWidth />
              </Box>
              <Box sx={{ px: 1.25, py: 1, borderRadius: '9px', background: isDark ? 'rgba(34,211,238,0.07)' : 'rgba(34,211,238,0.05)', border: `1px solid ${alpha('#22d3ee', 0.2)}` }}>
                <Typography sx={{ fontSize: '0.65rem', color: isDark ? '#22d3ee' : '#0891b2', fontWeight: 500, lineHeight: 1.5 }}>
                  We will poll this endpoint every 15 minutes. Expected: JSON object or array.
                </Typography>
              </Box>
              <Box component="button" sx={{ width: '100%', border: 'none', cursor: 'pointer', py: 0.9, borderRadius: '10px', background: 'linear-gradient(135deg, #22d3ee, #818cf8)', color: '#fff', fontSize: '0.78rem', fontWeight: 700, transition: 'all 0.18s ease', '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' } }}>
                Connect API
              </Box>
            </Box>
          )}

        </Box>
      </Box>
    </Modal>
  );
}

// ── Category badge shown at top of each form step ─────────────────────────────
function CategoryBadge({ cat, isDark, theme }: { cat: DataCategory; isDark: boolean; theme: Theme }) {
  const cfg = CATEGORY_CONFIG[cat];
  const Icon = CATEGORY_ICONS[cat];
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.75,
      px: 1, py: 0.5, borderRadius: '8px',
      background: isDark ? alpha(cfg.color, 0.12) : alpha(cfg.color, 0.08),
      border: `1px solid ${alpha(cfg.color, 0.25)}`,
      alignSelf: 'flex-start',
    }}>
      <Icon sx={{ fontSize: 13, color: cfg.color }} />
      <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: cfg.color }}>
        {cfg.emoji} {cfg.label}
      </Typography>
    </Box>
  );
}

