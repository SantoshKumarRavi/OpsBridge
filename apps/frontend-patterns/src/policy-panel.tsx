import { Card, CardContent, Typography } from '@mui/material';

export default function PolicyPanel() {
  return <Card variant="outlined"><CardContent>
    <Typography variant="h6">Lazy-loaded policy preview</Typography>
    <Typography color="text.secondary">React.lazy splits this optional panel into a separate client bundle.</Typography>
  </CardContent></Card>;
}
