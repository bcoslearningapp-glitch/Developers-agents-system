/* global test, expect */
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders Kaizen heading', () => {
  render(<App />);
  const heading = screen.getByRole('heading', { name: /Kaizen/i });
  expect(heading).toBeInTheDocument();
});
