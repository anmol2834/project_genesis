'use client';

import { useState, useRef, useEffect } from 'react';
import { Box, Typography, useTheme, alpha, Modal, IconButton, LinearProgress } from '@mui/material';
import CreditCardRoundedIcon from '@mui/icons-material/CreditCardRounded';
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import TrendingDownRoundedIcon from '@mui/icons-material/TrendingDownRounded';
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import StarRoundedIcon from '@mui/icons-material/StarRounded';
import FiberManualRecordRoundedIcon from '@mui/icons-material/FiberManualRecordRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import { lightGradients, darkGradients } from '@/theme/palette';
import {
  PLANS, CURRENT_PLAN, USAGE_STATS, INVOICES, PAYMENT_METHODS, COST_INSIGHTS,
} from './billingData';

// ── Animated counter ──────────────────────────────────────────────────────────
function CountUp({ target, decimals = 0 }: { target: number; decimals?: number }) {
  const [val, setVal] = useState(0);
  const frame = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / 900, 1);
      const v = (1 - Math.pow(1 - p, 3)) * target;
      setVal(parseFloat(v.toFixed(decimals)));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => { if (frame.current) cancelAnimationFrame(frame.current); };
  }, [target, decimals]);
  return <>{decimals > 0 ? val.toFixed(decimals) : val.toLocaleString()}</>;
}

// ── Glow chip ─────────────────────────────────────────────────────────────────
function GlowChip({ label, color, isDark }: { label: string; color: string; isDark: boolean }) {
  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.4, px: 0.75, py: 0.2, borderRadius: '6px', background: alpha(color, isDark ? 0.15 : 0.1), border: `1px solid ${alpha(color, isDark ? 0.3 : 0.2)}` }}>
      <FiberManualRecordRoundedIcon sx={{ fontSize: 6, color }} />
      <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color, lineHeight: 1 }}>{label}</Typography>
    </Box>
  );
}

// ── Section heading ───────────────────────────────────────────────────────────
function SectionHead({ title, subtitle, color, action }: { title: string; subtitle?: string; color: string; action?: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <Box sx={{ width: 3, height: 16, borderRadius: 2, background: color, flexShrink: 0 }} />
        <Box>
          <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.2 }}>{title}</Typography>
          {subtitle && <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.1 }}>{subtitle}</Typography>}
        </Box>
      </Box>
      {action}
    </Box>
  );
}

// ── Compact action button ─────────────────────────────────────────────────────
function Btn({ label, color = '#818cf8', onClick, icon: Icon, danger = false, isDark, size = 'sm' }: {
  label: string; color?: string; onClick?: () => void; icon?: React.ElementType;
  danger?: boolean; isDark: boolean; size?: 'xs' | 'sm' | 'md';
}) {
  const c = danger ? '#f87171' : color;
  const px = size === 'xs' ? 0.9 : size === 'md' ? 1.75 : 1.25;
  const py = size === 'xs' ? 0.3 : size === 'md' ? 0.75 : 0.55;
  const fs = size === 'xs' ? '0.62rem' : size === 'md' ? '0.78rem' : '0.72rem';
  return (
    <Box component="button" onClick={onClick} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, px, py, borderRadius: '8px', border: `1px solid ${alpha(c, isDark ? 0.3 : 0.22)}`, background: alpha(c, isDark ? 0.1 : 0.07), color: c, fontSize: fs, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s', '&:hover': { background: alpha(c, isDark ? 0.2 : 0.14), borderColor: alpha(c, 0.5), transform: 'translateY(-1px)' } }}>
      {Icon && <Icon sx={{ fontSize: size === 'xs' ? 11 : 13 }} />}
      {label}
    </Box>
  );
}

// ── Usage bar ─────────────────────────────────────────────────────────────────
function UsageBar({ stat, isDark }: { stat: typeof USAGE_STATS[0]; isDark: boolean }) {
  const pct = Math.min((stat.used / stat.limit) * 100, 100);
  const warn = pct >= 80;
  const danger = pct >= 95;
  const barColor = danger ? '#f87171' : warn ? '#fbbf24' : stat.color;
  return (
    <Box sx={{ py: 1, borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}`, '&:last-child': { borderBottom: 'none' } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.6, gap: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 500, color: 'text.primary', whiteSpace: 'nowrap' }}>{stat.label}</Typography>
          {warn && !danger && <WarningAmberRoundedIcon sx={{ fontSize: 12, color: '#fbbf24', flexShrink: 0 }} />}
          {danger && <WarningAmberRoundedIcon sx={{ fontSize: 12, color: '#f87171', flexShrink: 0 }} />}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
          <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary', whiteSpace: 'nowrap' }}>
            <Box component="span" sx={{ fontWeight: 700, color: barColor }}>{stat.used.toLocaleString()}</Box>
            {'/'}{stat.limit.toLocaleString()}
          </Typography>
          <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: barColor }}>{Math.round(pct)}%</Typography>
        </Box>
      </Box>
      <Box sx={{ height: 5, borderRadius: 3, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)', overflow: 'hidden' }}>
        <Box sx={{ height: '100%', borderRadius: 3, width: `${pct}%`, background: barColor, transition: 'width 0.9s ease', boxShadow: `0 0 6px ${alpha(barColor, 0.4)}` }} />
      </Box>
    </Box>
  );
}

// ── Plan upgrade modal ────────────────────────────────────────────────────────
function PlanModal({ open, onClose, isDark }: { open: boolean; onClose: () => void; isDark: boolean }) {
  const [selected, setSelected] = useState(CURRENT_PLAN.id);
  const [confirmed, setConfirmed] = useState(false);
  const theme = useTheme();

  const handleConfirm = () => { if (selected !== CURRENT_PLAN.id) setConfirmed(true); };
  const handleClose = () => { setConfirmed(false); setSelected(CURRENT_PLAN.id); onClose(); };

  return (
    <Modal open={open} onClose={handleClose} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Box sx={{ width: '100%', maxWidth: 520, borderRadius: '20px', outline: 'none', overflow: 'hidden', background: isDark ? 'linear-gradient(145deg,#1e293b 0%,#0f172a 100%)' : 'linear-gradient(145deg,#fff 0%,#f8fafc 100%)', border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'}`, boxShadow: isDark ? '0 32px 80px rgba(0,0,0,0.6)' : '0 32px 80px rgba(15,23,42,0.18)', animation: 'mIn 0.22s ease-out', '@keyframes mIn': { from: { opacity: 0, transform: 'scale(0.96) translateY(8px)' }, to: { opacity: 1, transform: 'scale(1) translateY(0)' } } }}>
        <Box sx={{ px: 2.5, pt: 2.5, pb: 2, borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)'}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box>
            <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>Change Plan</Typography>
            <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>Select a plan that fits your needs</Typography>
          </Box>
          <IconButton size="small" onClick={handleClose} sx={{ color: 'text.disabled', p: 0.5 }}><CloseRoundedIcon sx={{ fontSize: 16 }} /></IconButton>
        </Box>

        {!confirmed ? (
          <Box sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
            {PLANS.map(plan => {
              const isActive = plan.id === CURRENT_PLAN.id;
              const isSel = plan.id === selected;
              return (
                <Box key={plan.id} onClick={() => setSelected(plan.id)} sx={{ px: 1.75, py: 1.25, borderRadius: '12px', cursor: 'pointer', border: `1.5px solid ${isSel ? alpha(plan.color, 0.5) : isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`, background: isSel ? alpha(plan.color, isDark ? 0.1 : 0.06) : 'transparent', transition: 'all 0.15s', '&:hover': { borderColor: alpha(plan.color, 0.35) } }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', background: plan.color, boxShadow: isSel ? `0 0 8px ${alpha(plan.color, 0.7)}` : 'none', transition: 'all 0.2s' }} />
                      <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: isSel ? plan.color : 'text.primary' }}>{plan.name}</Typography>
                      {plan.popular && <GlowChip label="Popular" color={plan.color} isDark={isDark} />}
                      {isActive && <GlowChip label="Current" color="#34d399" isDark={isDark} />}
                    </Box>
                    <Typography sx={{ fontSize: '0.9rem', fontWeight: 800, color: plan.color }}>${plan.price}<Box component="span" sx={{ fontSize: '0.62rem', fontWeight: 500, color: 'text.disabled' }}>/mo</Box></Typography>
                  </Box>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.75 }}>
                    {plan.features.slice(0, 3).map(f => (
                      <Box key={f} sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                        <CheckRoundedIcon sx={{ fontSize: 10, color: plan.color }} />
                        <Typography sx={{ fontSize: '0.62rem', color: 'text.secondary' }}>{f}</Typography>
                      </Box>
                    ))}
                  </Box>
                </Box>
              );
            })}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 0.5 }}>
              <Btn label="Cancel" isDark={isDark} onClick={handleClose} />
              <Btn label="Confirm change" color="#818cf8" icon={CheckRoundedIcon} onClick={handleConfirm} isDark={isDark} size="md" />
            </Box>
          </Box>
        ) : (
          <Box sx={{ p: 2.5, textAlign: 'center' }}>
            <Box sx={{ width: 52, height: 52, borderRadius: '14px', mx: 'auto', mb: 1.5, background: alpha('#34d399', isDark ? 0.15 : 0.1), border: `1px solid ${alpha('#34d399', 0.3)}`, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: `0 0 20px ${alpha('#34d399', 0.3)}`, animation: 'popIn 0.3s cubic-bezier(0.34,1.56,0.64,1)', '@keyframes popIn': { from: { transform: 'scale(0.7)', opacity: 0 }, to: { transform: 'scale(1)', opacity: 1 } } }}>
              <CheckRoundedIcon sx={{ fontSize: 24, color: '#34d399' }} />
            </Box>
            <Typography sx={{ fontSize: '0.9rem', fontWeight: 800, color: 'text.primary', mb: 0.5 }}>Plan updated!</Typography>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', lineHeight: 1.6, mb: 2 }}>Your plan has been changed. Changes take effect immediately.</Typography>
            <Btn label="Done" color="#818cf8" onClick={handleClose} isDark={isDark} size="md" />
          </Box>
        )}
      </Box>
    </Modal>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function BillingPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const [planModalOpen, setPlanModalOpen] = useState(false);

  const statusColor = { paid: '#34d399', pending: '#fbbf24', failed: '#f87171' } as const;
  const statusLabel = { paid: 'Paid', pending: 'Pending', failed: 'Failed' } as const;

  const nearLimit = USAGE_STATS.filter(s => (s.used / s.limit) >= 0.8);

  return (
    <Box sx={{ flex: 1, overflowY: 'auto', minHeight: 0, '&::-webkit-scrollbar': { width: 4 }, '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.18), borderRadius: 2 } }}>
      <PlanModal open={planModalOpen} onClose={() => setPlanModalOpen(false)} isDark={isDark} />

      <Box sx={{ px: { xs: 2, sm: 3 }, pt: 2.5, pb: 5, display: 'flex', flexDirection: 'column', gap: 3 }}>

        {/* ── Page header ── */}
        <Box sx={{ animation: 'fadeDown 0.3s ease-out', '@keyframes fadeDown': { from: { opacity: 0, transform: 'translateY(-6px)' }, to: { opacity: 1, transform: 'translateY(0)' } } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.3 }}>
            <Typography sx={{ fontSize: { xs: '1.1rem', sm: '1.3rem' }, fontWeight: 900, letterSpacing: '-0.03em', color: 'text.primary', lineHeight: 1 }}>Billing</Typography>
            <GlowChip label="Pro Plan" color="#818cf8" isDark={isDark} />
          </Box>
          <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>Manage your plan, usage, and payments</Typography>
        </Box>

        {/* ── Billing alerts ── */}
        {nearLimit.length > 0 && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
            {nearLimit.map(s => {
              const pct = Math.round((s.used / s.limit) * 100);
              const isDanger = pct >= 95;
              const c = isDanger ? '#f87171' : '#fbbf24';
              return (
                <Box key={s.label} sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 1, borderRadius: '11px', background: alpha(c, isDark ? 0.08 : 0.05), border: `1px solid ${alpha(c, isDark ? 0.25 : 0.18)}` }}>
                  <WarningAmberRoundedIcon sx={{ fontSize: 15, color: c, flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '0.73rem', color: 'text.primary', flex: 1 }}>
                    <Box component="span" sx={{ fontWeight: 700, color: c }}>{s.label}</Box> is at {pct}% of your limit. {isDanger ? 'Upgrade now to avoid disruption.' : 'Consider upgrading soon.'}
                  </Typography>
                  <Btn label="Upgrade" color={c} onClick={() => setPlanModalOpen(true)} isDark={isDark} size="xs" />
                </Box>
              );
            })}
          </Box>
        )}

        {/* ── Two-column top: Current plan + Cost insights ── */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>

          {/* Current plan */}
          <Box sx={{ borderRadius: '16px', overflow: 'hidden', border: `1px solid ${alpha(CURRENT_PLAN.color, isDark ? 0.3 : 0.2)}`, background: isDark ? `linear-gradient(145deg,${alpha(CURRENT_PLAN.color, 0.12)} 0%,rgba(15,23,42,0.5) 100%)` : `linear-gradient(145deg,${alpha(CURRENT_PLAN.color, 0.07)} 0%,rgba(248,250,252,0.8) 100%)`, backdropFilter: 'blur(12px)', position: 'relative' }}>
            <Box sx={{ position: 'absolute', top: -30, right: -30, width: 120, height: 120, borderRadius: '50%', background: alpha(CURRENT_PLAN.color, isDark ? 0.12 : 0.08), filter: 'blur(30px)', pointerEvents: 'none' }} />
            <Box sx={{ px: 2, pt: 2, pb: 2, position: 'relative' }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1.5 }}>
                <Box>
                  <Typography sx={{ fontSize: '0.62rem', fontWeight: 800, letterSpacing: '0.09em', textTransform: 'uppercase', color: 'text.disabled', mb: 0.4 }}>Current Plan</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5 }}>
                    <Typography sx={{ fontSize: '1.6rem', fontWeight: 900, color: CURRENT_PLAN.color, letterSpacing: '-0.04em', lineHeight: 1 }}>{CURRENT_PLAN.name}</Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>plan</Typography>
                  </Box>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography sx={{ fontSize: '1.4rem', fontWeight: 900, color: 'text.primary', letterSpacing: '-0.04em', lineHeight: 1 }}>${CURRENT_PLAN.price}</Typography>
                  <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>per month</Typography>
                </Box>
              </Box>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mb: 2 }}>
                {[
                  { label: 'Status',           value: 'Active',                  color: '#34d399' },
                  { label: 'Billing cycle',    value: 'Monthly',                 color: 'text.secondary' },
                  { label: 'Next billing',     value: CURRENT_PLAN.nextBillingDate, color: 'text.secondary' },
                  { label: 'Member since',     value: CURRENT_PLAN.startDate,    color: 'text.secondary' },
                ].map(row => (
                  <Box key={row.label} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>{row.label}</Typography>
                    <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: row.color }}>{row.value}</Typography>
                  </Box>
                ))}
              </Box>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Btn label="Change plan" color={CURRENT_PLAN.color} icon={BoltRoundedIcon} onClick={() => setPlanModalOpen(true)} isDark={isDark} size="md" />
                <Btn label="Cancel" danger isDark={isDark} />
              </Box>
            </Box>
          </Box>

          {/* Cost insights */}
          <Box>
            <SectionHead title="Cost Insights" subtitle="Usage economics this month" color="#22d3ee" />
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
              {COST_INSIGHTS.map(ins => (
                <Box key={ins.label} sx={{ px: 1.5, py: 1.25, borderRadius: '12px', background: isDark ? alpha(ins.color, 0.07) : alpha(ins.color, 0.04), border: `1px solid ${alpha(ins.color, isDark ? 0.18 : 0.12)}`, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.4, gap: 0.5 }}>
                    <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{ins.label}</Typography>
                    {ins.trend === 'down'
                      ? <TrendingDownRoundedIcon sx={{ fontSize: 13, color: '#34d399', flexShrink: 0 }} />
                      : <TrendingUpRoundedIcon sx={{ fontSize: 13, color: ins.color, flexShrink: 0 }} />}
                  </Box>
                  <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: ins.color, letterSpacing: '-0.03em', lineHeight: 1 }}>{ins.value}</Typography>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>

        {/* ── Usage & limits ── */}
        <Box>
          <SectionHead title="Usage & Limits" subtitle="Current billing period" color="#818cf8" action={<Btn label="Upgrade limits" color="#818cf8" icon={BoltRoundedIcon} onClick={() => setPlanModalOpen(true)} isDark={isDark} size="xs" />} />
          <Box sx={{ borderRadius: '14px', border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`, background: isDark ? 'linear-gradient(145deg,rgba(30,41,59,0.6) 0%,rgba(15,23,42,0.4) 100%)' : 'linear-gradient(145deg,rgba(255,255,255,0.85) 0%,rgba(248,250,252,0.65) 100%)', backdropFilter: 'blur(12px)', px: 1.75, py: 0.5 }}>
            {USAGE_STATS.map(s => <UsageBar key={s.label} stat={s} isDark={isDark} />)}
          </Box>
        </Box>

        {/* ── Two-column: Payment methods + Invoices ── */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '340px 1fr' }, gap: 2 }}>

          {/* Payment methods */}
          <Box>
            <SectionHead title="Payment Methods" subtitle="Saved cards" color="#34d399" action={<Btn label="Add card" color="#34d399" icon={AddRoundedIcon} isDark={isDark} size="xs" />} />
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
              {PAYMENT_METHODS.map(pm => (
                <Box key={pm.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 1.1, borderRadius: '12px', border: `1px solid ${pm.isDefault ? alpha('#34d399', isDark ? 0.3 : 0.2) : isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`, background: pm.isDefault ? alpha('#34d399', isDark ? 0.07 : 0.04) : isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)', transition: 'all 0.15s' }}>
                  <Box sx={{ width: 36, height: 26, borderRadius: '6px', background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <CreditCardRoundedIcon sx={{ fontSize: 16, color: pm.isDefault ? '#34d399' : 'text.secondary' }} />
                  </Box>
                  <Box sx={{ flex: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <Typography sx={{ fontSize: '0.76rem', fontWeight: 600, color: 'text.primary' }}>{pm.brand} ···· {pm.last4}</Typography>
                      {pm.isDefault && <GlowChip label="Default" color="#34d399" isDark={isDark} />}
                    </Box>
                    <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>Expires {pm.expiry}</Typography>
                  </Box>
                  <IconButton size="small" sx={{ color: 'text.disabled', p: 0.4, '&:hover': { color: '#f87171' } }}>
                    <DeleteOutlineRoundedIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                </Box>
              ))}
            </Box>
          </Box>

          {/* Invoices */}
          <Box>
            <SectionHead title="Invoice History" subtitle="All past payments" color="#fbbf24" />
            <Box sx={{ borderRadius: '14px', border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`, background: isDark ? 'linear-gradient(145deg,rgba(30,41,59,0.6) 0%,rgba(15,23,42,0.4) 100%)' : 'linear-gradient(145deg,rgba(255,255,255,0.85) 0%,rgba(248,250,252,0.65) 100%)', backdropFilter: 'blur(12px)', overflow: 'hidden' }}>
              {/* Table header — hidden on xs, shown sm+ */}
              <Box sx={{ display: { xs: 'none', sm: 'grid' }, gridTemplateColumns: '1fr 90px 110px 60px', px: 1.75, py: 0.75, background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)', borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}` }}>
                {['Description', 'Date', 'Amount', ''].map(h => (
                  <Typography key={h} sx={{ fontSize: '0.58rem', fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'text.disabled' }}>{h}</Typography>
                ))}
              </Box>
              {INVOICES.map((inv, i) => (
                <Box key={inv.id} sx={{ borderBottom: i < INVOICES.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'}` : 'none', transition: 'background 0.12s', '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)' } }}>
                  {/* Desktop row */}
                  <Box sx={{ display: { xs: 'none', sm: 'grid' }, gridTemplateColumns: '1fr 90px 110px 60px', alignItems: 'center', px: 1.75, py: 1 }}>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography sx={{ fontSize: '0.74rem', fontWeight: 500, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{inv.description}</Typography>
                      <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>{inv.id}</Typography>
                    </Box>
                    <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>{inv.date}</Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <Typography sx={{ fontSize: '0.76rem', fontWeight: 700, color: 'text.primary' }}>${inv.amount}</Typography>
                      <GlowChip label={statusLabel[inv.status]} color={statusColor[inv.status]} isDark={isDark} />
                    </Box>
                    <Box component="button" sx={{ display: 'flex', alignItems: 'center', gap: 0.4, px: 0.75, py: 0.3, borderRadius: '6px', border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`, background: 'transparent', color: 'text.secondary', fontSize: '0.62rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s', '&:hover': { color: '#818cf8', borderColor: alpha('#818cf8', 0.4) } }}>
                      <DownloadRoundedIcon sx={{ fontSize: 11 }} />PDF
                    </Box>
                  </Box>
                  {/* Mobile row — stacked */}
                  <Box sx={{ display: { xs: 'flex', sm: 'none' }, alignItems: 'center', gap: 1, px: 1.5, py: 1 }}>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography sx={{ fontSize: '0.73rem', fontWeight: 600, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{inv.description}</Typography>
                      <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', mt: 0.15 }}>{inv.date} · {inv.id}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexShrink: 0 }}>
                      <Typography sx={{ fontSize: '0.76rem', fontWeight: 700, color: 'text.primary' }}>${inv.amount}</Typography>
                      <GlowChip label={statusLabel[inv.status]} color={statusColor[inv.status]} isDark={isDark} />
                      <Box component="button" sx={{ display: 'flex', alignItems: 'center', p: 0.4, borderRadius: '6px', border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`, background: 'transparent', color: 'text.secondary', cursor: 'pointer', transition: 'all 0.15s', '&:hover': { color: '#818cf8' } }}>
                        <DownloadRoundedIcon sx={{ fontSize: 13 }} />
                      </Box>
                    </Box>
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
