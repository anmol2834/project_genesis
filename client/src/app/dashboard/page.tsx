'use client';

import { Box, useTheme, alpha } from '@mui/material';
import WelcomeBanner from '@/components/dashboard/WelcomeBanner';
import StatsOverview from '@/components/dashboard/StatsOverview';
import InboxPreview from '@/components/dashboard/InboxPreview';
import AIActivityPanel from '@/components/dashboard/AIActivityPanel';
import QuickActions from '@/components/dashboard/QuickActions';
import EmailChart from '@/components/dashboard/EmailChart';

export default function DashboardPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return (
    <Box sx={{
      flex: 1,
      overflowY: 'auto',
      px: { xs: 2, sm: 3 },
      py: { xs: 2, sm: 2.5 },
      '&::-webkit-scrollbar': { width: 4 },
      '&::-webkit-scrollbar-track': { background: 'transparent' },
      '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
    }}>
      <Box sx={{ maxWidth: 1200, mx: 'auto', display: 'flex', flexDirection: 'column', gap: 2.5, pb: 4 }}>
        <WelcomeBanner />
        <StatsOverview />
        <EmailChart />
        <QuickActions />
        <Box sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: '1fr 340px' },
          gap: 2, alignItems: 'start',
        }}>
          <InboxPreview />
          <AIActivityPanel />
        </Box>
      </Box>
    </Box>
  );
}
