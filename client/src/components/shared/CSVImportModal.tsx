'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Box, Typography, useTheme, alpha, Modal, IconButton } from '@mui/material';
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import InsertDriveFileRoundedIcon from '@mui/icons-material/InsertDriveFileRounded';
import FiberManualRecordRoundedIcon from '@mui/icons-material/FiberManualRecordRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';

type Step = 'upload' | 'loading' | 'done';

function GlowChip({ label, color, isDark }: { label: string; color: string; isDark: boolean }) {
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.35,
      px: 0.65, py: 0.15, borderRadius: '5px',
      background: alpha(color, isDark ? 0.15 : 0.1),
      border: `1px solid ${alpha(color, isDark ? 0.3 : 0.2)}`,
    }}>
      <FiberManualRecordRoundedIcon sx={{ fontSize: 5, color }} />
      <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color, lineHeight: 1 }}>{label}</Typography>
    </Box>
  );
}

const IMPORT_HISTORY = [
  { name: 'leads_q4_2025.csv',   rows: 842,  date: '1 hour ago' },
  { name: 'enterprise_list.csv', rows: 1240, date: '2 days ago'  },
  { name: 'cold_outreach.csv',   rows: 1338, date: '5 days ago'  },
];

const REQUIRED_COLS = ['email', 'first_name', 'last_name'];
const TOTAL_ROWS = 842;

export default function CSVImportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const color = '#34d399';
  const router = useRouter();

  const [step, setStep] = useState<Step>('upload');
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [processed, setProcessed] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (step !== 'loading') return;
    setProgress(0); setProcessed(0);
    timer.current = setInterval(() => {
      setProgress(p => {
        const next = p + Math.random() * 7 + 3;
        if (next >= 100) {
          clearInterval(timer.current!);
          setProcessed(TOTAL_ROWS);
          setTimeout(() => setStep('done'), 350);
          return 100;
        }
        setProcessed(Math.round((next / 100) * TOTAL_ROWS));
        return next;
      });
    }, 110);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [step]);

  const startImport = (f: File) => { setFile(f); setStep('loading'); };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) startImport(f);
  };

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) startImport(f);
  };

  const reset = () => {
    if (timer.current) clearInterval(timer.current);
    setStep('upload'); setFile(null); setProgress(0); setProcessed(0);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleClose = () => { reset(); onClose(); };

  const handleViewLeads = () => { reset(); onClose(); router.push('/dashboard/leads'); };

  const divider = `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`;
  const rowDivider = `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}`;

  return (
    <Modal open={open} onClose={step === 'loading' ? undefined : handleClose}
      sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Box sx={{
        width: '100%', maxWidth: 460, borderRadius: '20px', outline: 'none', overflow: 'hidden',
        background: isDark ? 'linear-gradient(145deg,#1e293b 0%,#0f172a 100%)' : 'linear-gradient(145deg,#fff 0%,#f8fafc 100%)',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'}`,
        boxShadow: isDark ? '0 32px 80px rgba(0,0,0,0.6)' : '0 32px 80px rgba(15,23,42,0.18)',
        animation: 'mIn 0.22s ease-out',
        '@keyframes mIn': { from: { opacity: 0, transform: 'scale(0.96) translateY(8px)' }, to: { opacity: 1, transform: 'scale(1) translateY(0)' } },
      }}>

        {/* Header */}
        <Box sx={{ px: 2.5, pt: 2.5, pb: 2, borderBottom: divider, display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box sx={{ width: 36, height: 36, borderRadius: '10px', flexShrink: 0, background: alpha(color, isDark ? 0.18 : 0.1), border: `1px solid ${alpha(color, 0.25)}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <UploadFileRoundedIcon sx={{ fontSize: 18, color }} />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>Import CSV</Typography>
            <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>Upload a file to import leads — repeat anytime</Typography>
          </Box>
          {step !== 'loading' && (
            <IconButton size="small" onClick={handleClose} sx={{ color: 'text.disabled', p: 0.5 }}>
              <CloseRoundedIcon sx={{ fontSize: 16 }} />
            </IconButton>
          )}
        </Box>

        {/* Body */}
        <Box sx={{ px: 2.5, py: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>

          {/* UPLOAD */}
          {step === 'upload' && (
            <>
              <Box
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                sx={{
                  borderRadius: '14px', cursor: 'pointer', transition: 'all 0.2s ease',
                  border: `2px dashed ${dragging ? color : isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}`,
                  background: dragging ? alpha(color, isDark ? 0.1 : 0.05) : isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
                  py: 3.5, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1,
                  '&:hover': { borderColor: color, background: alpha(color, isDark ? 0.07 : 0.04) },
                }}>
                <Box sx={{ width: 44, height: 44, borderRadius: '12px', background: alpha(color, isDark ? 0.15 : 0.1), display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'transform 0.2s', transform: dragging ? 'scale(1.1)' : 'scale(1)' }}>
                  <UploadFileRoundedIcon sx={{ fontSize: 22, color }} />
                </Box>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary' }}>
                    {dragging ? 'Drop your file here' : 'Drag & drop or click to upload'}
                  </Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.25 }}>CSV or Excel files · Max 10MB</Typography>
                </Box>
                <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" style={{ display: 'none' }} onChange={handleInput} />
              </Box>

              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <Typography sx={{ fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.09em', textTransform: 'uppercase', color: 'text.disabled' }}>Required columns</Typography>
                  <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>· all others optional</Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {REQUIRED_COLS.map(col => (
                    <Box key={col} sx={{ px: 0.75, py: 0.25, borderRadius: '6px', background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)', border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}` }}>
                      <Typography sx={{ fontSize: '0.62rem', fontWeight: 600, color: 'text.secondary', fontFamily: 'monospace' }}>{col}</Typography>
                    </Box>
                  ))}
                </Box>
              </Box>

              <Box>
                <Typography sx={{ fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.09em', textTransform: 'uppercase', color: 'text.disabled', mb: 0.75 }}>Recent imports</Typography>
                <Box sx={{ borderRadius: '12px', border: divider, overflow: 'hidden', background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)' }}>
                  {IMPORT_HISTORY.map((h, i) => (
                    <Box key={h.name} sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 0.9, borderBottom: i < IMPORT_HISTORY.length - 1 ? rowDivider : 'none', transition: 'background 0.15s', '&:hover': { background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)' } }}>
                      <Box sx={{ width: 28, height: 28, borderRadius: '8px', flexShrink: 0, background: alpha(color, isDark ? 0.12 : 0.08), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <InsertDriveFileRoundedIcon sx={{ fontSize: 13, color }} />
                      </Box>
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography sx={{ fontSize: '0.73rem', fontWeight: 600, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.name}</Typography>
                        <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>{h.rows.toLocaleString()} leads · {h.date}</Typography>
                      </Box>
                      <GlowChip label={`${h.rows.toLocaleString()} leads`} color={color} isDark={isDark} />
                    </Box>
                  ))}
                </Box>
              </Box>
            </>
          )}

          {/* LOADING */}
          {step === 'loading' && file && (
            <Box sx={{ py: 0.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 1.1, borderRadius: '12px', background: alpha(color, isDark ? 0.08 : 0.05), border: `1px solid ${alpha(color, isDark ? 0.2 : 0.12)}` }}>
                <Box sx={{ width: 36, height: 36, borderRadius: '9px', flexShrink: 0, background: alpha(color, isDark ? 0.18 : 0.12), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <InsertDriveFileRoundedIcon sx={{ fontSize: 18, color }} />
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</Typography>
                  <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{(file.size / 1024).toFixed(1)} KB</Typography>
                </Box>
                <Typography sx={{ fontSize: '0.8rem', fontWeight: 800, color, flexShrink: 0 }}>{Math.round(progress)}%</Typography>
              </Box>

              <Box>
                <Box sx={{ height: 5, borderRadius: 3, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)', overflow: 'hidden' }}>
                  <Box sx={{ height: '100%', borderRadius: 3, width: `${progress}%`, background: `linear-gradient(90deg,${color},${alpha(color, 0.7)})`, transition: 'width 0.25s ease', boxShadow: `0 0 8px ${alpha(color, 0.5)}` }} />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.75 }}>
                  <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>Processing leads…</Typography>
                  <Typography sx={{ fontSize: '0.62rem', fontWeight: 600, color }}>{processed.toLocaleString()} / {TOTAL_ROWS.toLocaleString()}</Typography>
                </Box>
              </Box>

              <Box sx={
{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                {[
                  { label: 'Parsing file structure',    threshold: 0  },
                  { label: 'Validating required fields', threshold: 28 },
                  { label: 'Deduplicating records',      threshold: 55 },
                  { label: 'Importing to leads list',    threshold: 78 },
                ].map(s => {
                  const done = progress >= s.threshold + 22;
                  const active = progress >= s.threshold && !done;
                  return (
                    <Box key={s.label} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.3s ease', background: done ? alpha(color, isDark ? 0.2 : 0.12) : active ? alpha(color, isDark ? 0.1 : 0.07) : isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', border: `1px solid ${done ? alpha(color, 0.4) : active ? alpha(color, 0.25) : isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}` }}>
                        {done
                          ? <CheckRoundedIcon sx={{ fontSize: 10, color }} />
                          : active
                            ? <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: color, animation: 'pulse 1s ease-in-out infinite', '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } } }} />
                            : <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)' }} />
                        }
                      </Box>
                      <Typography sx={{ fontSize: '0.72rem', fontWeight: done || active ? 600 : 400, color: done ? color : active ? 'text.primary' : 'text.disabled', transition: 'color 0.3s ease' }}>
                        {s.label}
                      </Typography>
                    </Box>
                  );
                })}
              </Box>
            </Box>
          )}

          {/* DONE */}
          {step === 'done' && (
            <Box sx={{ textAlign: 'center', py: 1 }}>
              <Box sx={{ width: 56, height: 56, borderRadius: '16px', mx: 'auto', mb: 1.75, background: alpha(color, isDark ? 0.15 : 0.1), border: `1px solid ${alpha(color, 0.3)}`, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: `0 0 24px ${alpha(color, 0.35)}`, animation: 'popIn 0.3s cubic-bezier(0.34,1.56,0.64,1)', '@keyframes popIn': { from: { transform: 'scale(0.7)', opacity: 0 }, to: { transform: 'scale(1)', opacity: 1 } } }}>
                <CheckRoundedIcon sx={{ fontSize: 26, color }} />
              </Box>
              <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: 'text.primary', mb: 0.5, letterSpacing: '-0.02em' }}>Import complete</Typography>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', lineHeight: 1.6, mb: 2 }}>
                {file && <Box component="span" sx={{ fontWeight: 600, color: 'text.primary' }}>{file.name}</Box>}{' '}
                was imported successfully. {TOTAL_ROWS.toLocaleString()} leads are now in your list.
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 1 }}>
                {[
                  { label: 'Imported',   value: TOTAL_ROWS.toLocaleString(), color },
                  { label: 'Duplicates', value: '14',  color: '#fbbf24' },
                  { label: 'Skipped',    value: '3',   color: '#94a3b8' },
                ].map(s => (
                  <Box key={s.label} sx={{ px: 1, py: 0.9, borderRadius: '10px', textAlign: 'center', background: isDark ? alpha(s.color, 0.08) : alpha(s.color, 0.05), border: `1px solid ${alpha(s.color, isDark ? 0.18 : 0.12)}` }}>
                    <Typography sx={{ fontSize: '1rem', fontWeight: 900, color: s.color, lineHeight: 1, letterSpacing: '-0.03em' }}>{s.value}</Typography>
                    <Typography sx={{ fontSize: '0.58rem', color: 'text.disabled', mt: 0.2 }}>{s.label}</Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </Box>

        {/* Footer */}
        <Box sx={{ px: 2.5, pb: 2.5, pt: 0.5, display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
          {step === 'upload' && (
            <Box component="button" onClick={() => fileRef.current?.click()} sx={{ px: 1.75, py: 0.75, borderRadius: '10px', border: 'none', cursor: 'pointer', background: `linear-gradient(135deg,${color},${alpha(color, 0.7)})`, color: '#fff', fontSize: '0.78rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 0.6, transition: 'opacity 0.15s,transform 0.15s', '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' } }}>
              <UploadFileRoundedIcon sx={{ fontSize: 15 }} />
              Choose file
            </Box>
          )}
          {step === 'loading' && (
            <Box sx={{ px: 1.75, py: 0.75, borderRadius: '10px', background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)', border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`, display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Box sx={{ width: 12, height: 12, borderRadius: '50%', border: `2px solid ${alpha(color, 0.3)}`, borderTopColor: color, animation: 'spin 0.8s linear infinite', '@keyframes spin': { to: { transform: 'rotate(360deg)' } } }} />
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'text.secondary' }}>Importing…</Typography>
            </Box>
          )}
          {step === 'done' && (
            <>
              <Box component="button" onClick={reset} sx={{ px: 1.25, py: 0.55, borderRadius: '9px', cursor: 'pointer', border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}`, background: 'transparent', color: theme.palette.text.secondary, fontSize: '0.72rem', fontWeight: 600, transition: 'all 0.15s', '&:hover': { background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)' } }}>
                Import another
              </Box>
              <Box component="button" onClick={handleViewLeads} sx={{ px: 1.75, py: 0.75, borderRadius: '10px', border: 'none', cursor: 'pointer', background: isDark ? 'rgba(129,140,248,0.2)' : 'rgba(67,56,202,0.1)', color: isDark ? '#818cf8' : '#4338ca', fontSize: '0.78rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 0.5, transition: 'opacity 0.15s', '&:hover': { opacity: 0.8 } }}>
                <PeopleRoundedIcon sx={{ fontSize: 14 }} />
                View leads
              </Box>
            </>
          )}
        </Box>
      </Box>
    </Modal>
  );
}
