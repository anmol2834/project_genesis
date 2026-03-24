'use client';

import { Box, Typography, useTheme, alpha } from '@mui/material';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import FilterAltRoundedIcon from '@mui/icons-material/FilterAltRounded';
import ForumRoundedIcon from '@mui/icons-material/ForumRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import SecurityRoundedIcon from '@mui/icons-material/SecurityRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import { motion } from 'framer-motion';
import { FadeUp, StaggerContainer, fadeUp } from './motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const FEATURES = [
  { icon: BoltRoundedIcon,        title: 'Zero-UI Auto Reply',     desc: 'Fully automated responses for routine emails. 85%+ confidence threshold before firing.', color: '#f59e0b', tag: 'Game-changer' },
  { icon: FilterAltRoundedIcon,   title: 'Smart Filtering',        desc: 'Never processes spam, marketing, or social notifications. Only real conversations.',       color: '#6366f1', tag: null          },
  { icon: ForumRoundedIcon,       title: 'Thread Intelligence',    desc: 'Full conversation history compressed and understood. Context never lost.',                  color: '#8b5cf6', tag: null          },
  { icon: CampaignRoundedIcon,    title: 'Campaign + Inbox Merge', desc: 'Campaign replies land in your unified inbox. One view for everything.',                    color: '#06b6d4', tag: null          },
  { icon: SecurityRoundedIcon,    title: 'AES-256 Encryption',     desc: 'All OAuth tokens encrypted at rest. Enterprise-grade security by default.',                color: '#10b981', tag: 'Enterprise'  },
  { icon: TrendingUpRoundedIcon,  title: 'Predictive Analytics',   desc: 'Forecast email volume, peak hours, and busy days before they happen.',                     color: '#ef4444', tag: null          },
];

export default function FeaturesSection() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box
      id="features"
      component="section"
      sx={{ py: { xs: 7, sm: 10, md: 14 }, px: { xs: 2, sm: 3, md: 4 } }}
    >
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
        <FadeUp>
          <Box sx={{ textAlign: 'center', mb: { xs: 5, sm: 7, md: 10 } }}>
            <Typography variant="overline" sx={{ color: 'primary.main', mb: 1, display: 'block' }}>
              Built different
            </Typography>
            <Typography
              variant="h2"
              sx={{ mb: 1.5, fontSize: { xs: 'clamp(1.5rem, 6vw, 2rem)', md: 'clamp(1.6rem, 4vw, 2.5rem)' } }}
            >
              Features that don't{' '}
              <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                exist elsewhere
              </Box>
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: 400, mx: 'auto', fontSize: { xs: '0.875rem', sm: '1rem' } }}>
              Every feature is engineered for speed, intelligence, and zero friction.
            </Typography>
          </Box>
        </FadeUp>

        <StaggerContainer>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: 'repeat(3, 1fr)' },
              gap: { xs: 1.5, sm: 2 },
            }}
          >
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <motion.div key={f.title} variants={fadeUp}>
                  <Box
                    sx={{
                      p: { xs: 2.5, sm: 3, md: 3.5 },
                      borderRadius: { xs: '12px', sm: '16px' },
                      height: '100%',
                      border: `1px solid ${theme.palette.divider}`,
                      background: theme.palette.background.paper,
                      position: 'relative', overflow: 'hidden',
                      transition: 'all 0.22s ease',
                      cursor: 'default',
                      '&:hover': {
                        borderColor: alpha(f.color, isDark ? 0.45 : 0.35),
                        boxShadow: `0 10px 32px ${alpha(f.color, isDark ? 0.12 : 0.08)}`,
                        transform: 'translateY(-3px)',
                        '& .feature-glow': { opacity: 1 },
                      },
                    }}
                  >
                    {/* Hover glow */}
                    <Box
                      className="feature-glow"
                      sx={{
                        position: 'absolute', top: 0, right: 0,
                        width: 100, height: 100,
                        background: `radial-gradient(circle, ${alpha(f.color, 0.12)} 0%, transparent 70%)`,
                        opacity: 0, transition: 'opacity 0.3s ease', pointerEvents: 'none',
                      }}
                    />

                    {f.tag && (
                      <Box
                        sx={{
                          position: 'absolute', top: 12, right: 12,
                          px: 0.875, py: 0.25, borderRadius: '5px',
                          background: alpha(f.color, isDark ? 0.18 : 0.10),
                          border: `1px solid ${alpha(f.color, isDark ? 0.35 : 0.22)}`,
                        }}
                      >
                        <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: f.color }}>{f.tag}</Typography>
                      </Box>
                    )}

                    <Box sx={{ width: { xs: 40, sm: 44 }, height: { xs: 40, sm: 44 }, borderRadius: '10px', mb: { xs: 2, sm: 2.5 }, background: alpha(f.color, isDark ? 0.15 : 0.09), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Icon sx={{ color: f.color, fontSize: { xs: 20, sm: 22 } }} />
                    </Box>

                    <Typography variant="h6" sx={{ mb: 0.75, fontSize: { xs: '0.875rem', sm: '1rem' } }}>{f.title}</Typography>
                    <Typography variant="body2" sx={{ color: 'text.secondary', lineHeight: 1.65, fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>{f.desc}</Typography>
                  </Box>
                </motion.div>
              );
            })}
          </Box>
        </StaggerContainer>
      </Box>
    </Box>
  );
}
