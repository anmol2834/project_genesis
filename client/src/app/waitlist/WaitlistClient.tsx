'use client';

import { useState } from 'react';
import { Box, Button, TextField, Typography, useTheme, alpha, CircularProgress } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import RocketLaunchRoundedIcon from '@mui/icons-material/RocketLaunchRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import NextLink from 'next/link';
import { lightGradients, darkGradients } from '@/theme/palette';

const MotionBox = motion.create(Box);

export default function WaitlistClient() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  const [formData, setFormData] = useState({ name: '', email: '', company: '' });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<'success' | 'error' | ''>('');

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);

    const formDataObj = new FormData(event.currentTarget);
    formDataObj.append('access_key', process.env.NEXT_PUBLIC_WEB3FORMS_ACCESS_KEY || '');
    formDataObj.append('subject', '🚀 New Waitlist Signup - Proxipilot');
    formDataObj.append('from_name', 'Proxipilot Waitlist');

    try {
      const response = await fetch('https://api.web3forms.com/submit', {
        method: 'POST',
        body: formDataObj,
      });
      const data = await response.json();
      setResult(data.success ? 'success' : 'error');
    } catch {
      setResult('error');
    } finally {
      setLoading(false);
    }
  };

  const benefits = [
    { icon: RocketLaunchRoundedIcon, text: 'Early access to all premium features', color: '#8b5cf6' },
    { icon: AutoAwesomeRoundedIcon, text: 'Exclusive AI-powered email templates', color: '#ec4899' },
    { icon: BoltRoundedIcon, text: 'Priority support & onboarding', color: '#f59e0b' },
    { icon: GroupsRoundedIcon, text: 'Join 2,500+ early adopters', color: '#10b981' },
  ];

  const stats = [
    { value: '2,500+', label: 'On Waitlist', icon: GroupsRoundedIcon },
    { value: '98%', label: 'Satisfaction', icon: CheckCircleRoundedIcon },
    { value: '10x', label: 'Faster Replies', icon: TrendingUpRoundedIcon },
  ];

  return (
    <Box sx={{ height: '100vh', width: '100vw', position: 'fixed', inset: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Animated Background */}
      <Box sx={{ position: 'absolute', inset: 0, zIndex: 0 }}>
        <Box sx={{ position: 'absolute', top: '10%', left: '5%', width: 350, height: 350, background: isDark ? 'radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)' : 'radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%)', animation: 'float 8s ease-in-out infinite' }} />
        <Box sx={{ position: 'absolute', bottom: '10%', right: '8%', width: 300, height: 300, background: isDark ? 'radial-gradient(circle, rgba(236,72,153,0.12) 0%, transparent 70%)' : 'radial-gradient(circle, rgba(236,72,153,0.06) 0%, transparent 70%)', animation: 'float 10s ease-in-out infinite reverse' }} />
        <Box sx={{ position: 'absolute', top: '45%', right: '15%', width: 200, height: 200, background: isDark ? 'radial-gradient(circle, rgba(245,158,11,0.10) 0%, transparent 70%)' : 'radial-gradient(circle, rgba(245,158,11,0.05) 0%, transparent 70%)', animation: 'float 12s ease-in-out infinite' }} />
      </Box>

      {/* Back Button */}
      <Box sx={{ position: 'absolute', top: 20, left: 20, zIndex: 10 }}>
        <Button component={NextLink} href="/" sx={{ color: 'text.secondary', '&:hover': { color: 'text.primary', background: alpha(theme.palette.primary.main, 0.05) } }}>
          ← Back
        </Button>
      </Box>

      {/* Main Content */}
      <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', zIndex: 1, px: { xs: 2, sm: 3, md: 4 } }}>
        <Box sx={{ maxWidth: 1000, width: '100%', display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.1fr 0.9fr' }, gap: { xs: 3, md: 5 }, alignItems: 'center' }}>
          {/* Left: Content */}
          <MotionBox initial={{ opacity: 0, x: -30 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6 }}>
            <MotionBox animate={{ y: [0, -6, 0] }} transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }} sx={{ display: 'inline-flex', alignItems: 'center', gap: 1, px: 2, py: 0.6, borderRadius: '50px', background: isDark ? alpha('#8b5cf6', 0.15) : alpha('#8b5cf6', 0.08), border: `1px solid ${alpha('#8b5cf6', 0.3)}`, mb: 2 }}>
              <Box sx={{ width: 7, height: 7, borderRadius: '50%', background: '#8b5cf6', boxShadow: '0 0 10px rgba(139,92,246,0.6)', animation: 'pulse 2s ease-in-out infinite' }} />
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#8b5cf6' }}>Limited Spots Available</Typography>
            </MotionBox>

            <Typography variant="h1" sx={{ fontSize: { xs: '1.75rem', sm: '2.25rem', md: '2.75rem' }, fontWeight: 800, mb: 1.5, background: isDark ? 'linear-gradient(135deg, #f8fafc 0%, #c7d2fe 100%)' : 'linear-gradient(135deg, #0f172a 0%, #3730a3 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', lineHeight: 1.15 }}>
              Join the Future of Email Automation
            </Typography>

            <Typography sx={{ fontSize: { xs: '0.9rem', sm: '1rem' }, color: 'text.secondary', mb: 3, lineHeight: 1.6 }}>
              Be among the first to experience AI-powered email management that saves <Box component="strong" sx={{ color: 'text.primary', fontWeight: 700 }}>20+ hours per week</Box>.
            </Typography>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, mb: 3 }}>
              {benefits.map((benefit, i) => (
                <MotionBox key={i} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + i * 0.1 }} sx={{ display: 'flex', alignItems: 'center', gap: 1.2 }}>
                  <Box sx={{ width: 32, height: 32, borderRadius: '8px', background: alpha(benefit.color, isDark ? 0.15 : 0.1), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <benefit.icon sx={{ fontSize: 16, color: benefit.color }} />
                  </Box>
                  <Typography sx={{ fontSize: '0.875rem', color: 'text.primary' }}>{benefit.text}</Typography>
                </MotionBox>
              ))}
            </Box>

            <Box sx={{ display: 'flex', gap: 3 }}>
              {stats.map((stat, i) => (
                <MotionBox key={i} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.6 + i * 0.1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.3 }}>
                    <stat.icon sx={{ fontSize: 14, color: 'primary.main' }} />
                    <Typography sx={{ fontSize: '1.25rem', fontWeight: 800, color: 'text.primary' }}>{stat.value}</Typography>
                  </Box>
                  <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>{stat.label}</Typography>
                </MotionBox>
              ))}
            </Box>
          </MotionBox>

          {/* Right: Form */}
          <MotionBox initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6, delay: 0.2 }}>
            <AnimatePresence mode="wait">
              {result === 'success' ? (
                <MotionBox key="success" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} sx={{ p: 3, borderRadius: '20px', background: isDark ? alpha('#10b981', 0.1) : alpha('#10b981', 0.05), border: `1px solid ${alpha('#10b981', 0.3)}`, textAlign: 'center' }}>
                  <MotionBox animate={{ scale: [1, 1.1, 1] }} transition={{ duration: 0.5 }}>
                    <CheckCircleRoundedIcon sx={{ fontSize: 56, color: '#10b981', mb: 1.5 }} />
                  </MotionBox>
                  <Typography variant="h5" sx={{ fontWeight: 700, mb: 1, fontSize: '1.5rem', color: 'text.primary' }}>You&apos;re on the list! 🎉</Typography>
                  <Typography sx={{ color: 'text.secondary', mb: 2.5, fontSize: '0.9rem' }}>We&apos;ll notify you when we launch!</Typography>
                  <Button component={NextLink} href="/" variant="outlined" sx={{ borderColor: '#10b981', color: '#10b981', '&:hover': { borderColor: '#059669', background: alpha('#10b981', 0.1) } }}>
                    Back to Home
                  </Button>
                </MotionBox>
              ) : (
                <Box
                  component={motion.form}
                  key="form"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onSubmit={onSubmit}
                  sx={{ p: 3, borderRadius: '20px', background: isDark ? alpha(theme.palette.background.paper, 0.6) : alpha('#fff', 0.8), backdropFilter: 'blur(20px)', border: `1px solid ${alpha(theme.palette.primary.main, isDark ? 0.2 : 0.15)}`, boxShadow: isDark ? '0 20px 60px rgba(0,0,0,0.4)' : '0 20px 60px rgba(0,0,0,0.08)' }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.2, mb: 2.5 }}>
                    <Box sx={{ width: 44, height: 44, borderRadius: '12px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <RocketLaunchRoundedIcon sx={{ color: '#fff', fontSize: 22 }} />
                    </Box>
                    <Box>
                      <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.1rem' }}>Join Waitlist</Typography>
                      <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>Secure your early access</Typography>
                    </Box>
                  </Box>

                  <TextField fullWidth label="Full Name" name="name" required value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} sx={{ mb: 2 }} size="small" />
                  <TextField fullWidth label="Email Address" name="email" type="email" required value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} sx={{ mb: 2 }} size="small" />
                  <TextField fullWidth label="Company (Optional)" name="company" value={formData.company} onChange={(e) => setFormData({ ...formData, company: e.target.value })} sx={{ mb: 2.5 }} size="small" />

                  {result === 'error' && (
                    <Typography sx={{ color: 'error.main', fontSize: '0.8rem', mb: 1.5, textAlign: 'center' }}>
                      Something went wrong. Please try again.
                    </Typography>
                  )}

                  <Button type="submit" fullWidth variant="contained" disabled={loading} sx={{ minHeight: 48, fontSize: '0.95rem', fontWeight: 600, background: grad.primary, boxShadow: isDark ? '0 12px 32px rgba(139,92,246,0.3)' : '0 12px 32px rgba(139,92,246,0.2)', '&:hover': { transform: 'translateY(-2px)', boxShadow: isDark ? '0 16px 40px rgba(139,92,246,0.4)' : '0 16px 40px rgba(139,92,246,0.3)' }, transition: 'all 0.2s' }}>
                    {loading ? <CircularProgress size={22} sx={{ color: '#fff' }} /> : 'Join the Waitlist →'}
                  </Button>

                  <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', textAlign: 'center', mt: 1.5 }}>
                    By joining, you agree to receive updates about Proxipilot
                  </Typography>
                </Box>
              )}
            </AnimatePresence>
          </MotionBox>
        </Box>
      </Box>

      <style jsx global>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-20px) scale(1.05); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </Box>
  );
}
