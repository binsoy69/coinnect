import { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Uncaught React component error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-6 text-white text-center">
          <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-3xl p-8 max-w-lg w-full shadow-2xl">
            <div className="w-16 h-16 bg-red-500/20 border border-red-500/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">⚠️</span>
            </div>
            <h2 className="text-2xl font-bold mb-2">Display Error Occurred</h2>
            <p className="text-white/80 text-sm mb-6 leading-relaxed">
              An unexpected user interface error occurred. You can return to the start screen or reload the kiosk application.
            </p>
            <div className="bg-black/30 rounded-xl p-4 mb-6 text-left font-mono text-xs text-red-200 overflow-auto max-h-40 border border-white/10">
              {this.state.error?.toString()}
            </div>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null, errorInfo: null });
                window.location.href = '/';
              }}
              className="w-full bg-white text-coinnect-primary font-bold py-4 px-6 rounded-xl shadow-lg hover:bg-gray-100 transition-colors text-lg"
            >
              Return to Start Screen
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
