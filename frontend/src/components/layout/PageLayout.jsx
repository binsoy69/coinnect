import Header from '../common/Header';
import PageTransition from './PageTransition';

const bgVariants = {
  default: 'bg-surface-light',
  orange: 'bg-coinnect-primary',
  navy: 'bg-gradient-to-br from-coinnect-navy to-coinnect-navy-dark',
  ewallet: 'bg-coinnect-ewallet',
};

export default function PageLayout({
  children,
  variant = 'default',
  showHeader = true,
  headerProps = {},
  className = '',
  contentClassName = '',
  fullHeight = true,
}) {
  const headerVariant = variant === 'default' ? 'light' : 'dark';

  return (
    <PageTransition>
      <div
        className={`
          ${bgVariants[variant] || bgVariants.default}
          ${fullHeight ? 'min-h-screen' : ''}
          ${className}
        `}
      >
        <div className="max-w-7xl mx-auto px-8">
          {showHeader && (
            <Header variant={headerVariant} {...headerProps} />
          )}
          <main className={contentClassName}>
            {children}
          </main>
        </div>
      </div>
    </PageTransition>
  );
}
