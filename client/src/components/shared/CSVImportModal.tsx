'use client';

import { useState, useRef } from 'react';
import { Box, Typography, useTheme, alpha, Modal, IconButton } from '@mui/material';
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import FiberManualRecordRoundedIcon from '@mui/icons-material/FiberManualRecordRounded';

function GlowChip({ label, color, isDark }: { label: string; color: string; isDark: boolean }) {
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.35,
      px: 0.65, py: 0.15, borderRadius: '5px',
      background: alpha(color, isDark ? 0.15 : 0.1),
      border: `1px solid ${alpha(color, isDark ? 0.3 : 0.2)}`,
      boxShadow: `0 0 6px ${alpha(color, 0.18)}`,
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

export default function CSVImportModal({ open, onClose }: {
  open: boolean; onClose: () => void;
}) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [done, setDone] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const color = '#34d399';

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) { setFile(f); setDone(true); }
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) { setFile(f); setDone(true); }
  };

  const handleClose = () => { setFile(null); setDone(false); onClose(); };

  return (
    <Modal open={open} onClose={handleClose} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Box sx={{
        width: '100%', maxWidth: 460, borderRadius: '20px', outline: 'none',
        background: isDark ? 'linear-gradient(145deg, #1e293b 0%, #0f172a 100%)' : 'linear-gradient(145deg, #ffffff 0%, #f8fafc 100%)',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'}`,
        boxShadow: `0 32px 80px rgba(0,0,0,${isDark ? 0.6 : 0.18})`,
        overflow: 'hidden',
        animation: 'modalIn 0.22s ease-out',
        '@keyframes modalIn': { from: { opacity: 0, transform: 'scale(0.96) translateY(8px)' }, to: { opacity: 1, transform: 'scale(1) translateY(0)' } },
      }}>
        <Box sx={{ px: 2.5, pt: 2.5, pb: 2, borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)'}`, display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box sx={{ width: 36, height: 36, borderRadius: '10px', background: alpha(color, isDark ? 0.18 : 0.1), border: `1px solid ${alpha(color, 0.25)}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <UploadFileRoundedIcon sx={{ fontSize: 18, color }} />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>Import CSV</Typography>
            <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>Upload a file to import leads — repeat anytime</Typography>
          </Box>
          <IconButton size='small' onClick={handleClose} sx={{ color: 'text.disabled', p: 0.5 }}>
            <CloseRoundedIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Box>

        <Box sx={{ px: 2.5, py: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {!done ? (
            <>
              <Box
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                sx={{
                  borderRadius: '14px',
                  border: `2px dashed ${dragging ? color : isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}`,
                  background: dragging ? alpha(color, isDark ? 0.1 : 0.05) : isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
                  py: 3.5, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1,
                  cursor: 'pointer', transition: 'all 0.2s ease',
                  '&:hover': { borderColor: color, background: alpha(color, isDark ? 0.07 : 0.04) },
                }}>
                <Box sx={{ width: 44, height: 44, borderRadius: '12px', background: alpha(color, isDark ? 0.15 : 0.1), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <UploadFileRoundedIcon sx={{ fontSize: 22, color }} />
                </Box>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary' }}>
                    {dragging ? 'Drop your file here' : 'Drag & drop or click to upload'}
                  </Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.25 }}>CSV or Excel files · Max 10MB</Typography>
                </Box>
                <input ref={fileRef} type='file' accept='.csv,.xlsx,.xls' style={{ display: 'none' }} onChange={handleFile} />
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
                <Box sx={{ borderRadius: '12px', border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`, overflow: 'hidden', background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)' }}>
                  {IMPORT_HISTORY.map((h, i) => (
                    <Box key={h.name} sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 0.9, borderBottom: i < IMPORT_HISTORY.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` : 'none' }}>
                      <Box sx={{ width: 28, height: 28, borderRadius: '8px', background: alpha(color, isDark ? 0.12 : 0.08), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <CheckRoundedIcon sx={{ fontSize: 13, color }} />
                      </Box>
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography sx={{ fontSize: '0.73rem', fontWeight: 600, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.name}</Typography>
                        <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>{h.rows.toLocaleString()} leads · {h.date}</Typography>
                      </Box>
                      <GlowChip label={` leads`} color={color} isDark={isDark} />
                    </Box>
                  ))}
                </Box>
              </Box>
            </>
          ) : (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <Box sx={{ width: 52, height: 52, borderRadius: '14px', background: alpha(color, isDark ? 0.15 : 0.1), border: `1px solid ${alpha(color, 0.25)}`, display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 'auto', mb: 1.5, boxShadow: `0 0 20px ${alpha(color, 0.3)}` }}>
                <CheckRoundedIcon sx={{ fontSize: 24, color }} />
              </Box>
              <Typography sx={{ fontSize: '0.9rem', fontWeight: 800, color: 'text.primary', mb: 0.5 }}>Import started</Typography>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', lineHeight: 1.6 }}>
                {file && <Box component='span' sx={{ fontWeight: 600, color: 'text.primary' }}>{file.name}</Box>}
                {file && ' is'} being processed. Leads will appear in your Leads page shortly.
              </Typography>
            </Box>
          )}
        </Box>

        <Box sx={{ px: 2.5, pb: 2.5, pt: 0.5, display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
          {!done ? (
            <Box component='button' onClick={() => fileRef.current?.click()} sx={{
              px: 1.75, py: 0.75, borderRadius: '10px', border: 'none', cursor: 'pointer',
              background: `linear-gradient(135deg, ${color}, ${alpha(color, 0.7)})`,
              color: '#fff', fontSize: '0.78rem', fontWeight: 700,
              display: 'flex', alignItems: 'center', gap: 0.6,
              transition: 'opacity 0.15s, transform 0.15s',
              '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' },
            }}>
              <UploadFileRoundedIcon sx={{ fontSize: 15 }} />
              Choose file
            </Box>
          ) : (
            <>
              <Box component='button' onClick={() => { setFile(null); setDone(false); }} sx={{
                px: 1.25, py: 0.55, borderRadius: '9px', cursor: 'pointer',
                border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}`,
                background: 'transparent', color: theme.palette.text.secondary,
                fontSize: '0.72rem', fontWeight: 600,
                transition: 'all 0.15s', '&:hover': { background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)' },
              }}>
                Import another
              </Box>
              <Box component='button' onClick={handleClose} sx={{
                px: 1.75, py: 0.75, borderRadius: '10px', border: 'none', cursor: 'pointer',
                background: isDark ? 'rgba(129,140,248,0.2)' : 'rgba(67,56,202,0.1)',
                color: isDark ? '#818cf8' : '#4338ca',
                fontSize: '0.78rem', fontWeight: 700,
                transition: 'opacity 0.15s', '&:hover': { opacity: 0.8 },
              }}>
                View leads
              </Box>
            </>
          )}
        </Box>
      </Box>
    </Modal>
  );
}