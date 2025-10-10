import { useState, useEffect } from 'react'
import { billingAPI } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import DashboardLayout from '@/layouts/DashboardLayout'

interface Transaction {
  id: number
  amount: number
  currency: string
  status: string
  description: string | null
  payment_method: string | null
  created_at: string
}

interface Invoice {
  id: number
  invoice_number: string
  amount: number
  currency: string
  status: string
  period_start: string
  period_end: string
  paid_at: string | null
  due_date: string | null
  stripe_invoice_url: string | null
  stripe_pdf_url: string | null
  created_at: string
}

interface Subscription {
  tier: string
  active: boolean
  current_period_end?: number
  cancel_at_period_end?: boolean
}

interface CreditBalance {
  balance: number
  currency: string
}

const BillingPage = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [creditBalance, setCreditBalance] = useState<CreditBalance | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'overview' | 'transactions' | 'invoices'>('overview')
  const [selectedTier, setSelectedTier] = useState<string>('')
  const [showUpgradeModal, setShowUpgradeModal] = useState(false)
  const [showTopUpModal, setShowTopUpModal] = useState(false)
  const [topUpAmount, setTopUpAmount] = useState<string>('')
  const [customAmount, setCustomAmount] = useState<string>('')
  const [processingPayment, setProcessingPayment] = useState(false)
  const user = useAuthStore((state) => state.user)

  useEffect(() => {
    loadBillingData()
  }, [])

  const loadBillingData = async () => {
    try {
      setLoading(true)
      const [transactionsRes, invoicesRes, subscriptionRes, creditBalanceRes] = await Promise.all([
        billingAPI.getTransactions(),
        billingAPI.getInvoices(),
        billingAPI.getSubscription(),
        billingAPI.getCreditBalance(),
      ])
      
      setTransactions(transactionsRes.data)
      setInvoices(invoicesRes.data)
      setSubscription(subscriptionRes.data)
      setCreditBalance(creditBalanceRes.data)
    } catch (error) {
      console.error('Error loading billing data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleTopUp = async () => {
    const amount = parseFloat(topUpAmount || customAmount)
    
    if (!amount || amount < 5) {
      alert('Minimum top-up amount is $5.00')
      return
    }

    try {
      setProcessingPayment(true)
      const response = await billingAPI.topUpCredits({ amount })
      
      // In a real implementation, you would integrate Stripe Elements here
      // For now, we'll show a success message
      alert(`Payment intent created for $${amount.toFixed(2)}. In production, Stripe payment form would appear here.`)
      
      setShowTopUpModal(false)
      setTopUpAmount('')
      setCustomAmount('')
      
      // Reload billing data after successful top-up
      await loadBillingData()
    } catch (error: any) {
      console.error('Error processing top-up:', error)
      alert(error.response?.data?.detail || 'Failed to process top-up')
    } finally {
      setProcessingPayment(false)
    }
  }

  const quickAmounts = [5, 10, 25, 50, 100]

  const handleUpgradeSubscription = async () => {
    // This would typically integrate with Stripe Elements
    // For now, just show the UI
    alert('Stripe payment integration would go here')
  }

  const handleCancelSubscription = async () => {
    if (!confirm('Are you sure you want to cancel your subscription?')) return
    
    try {
      await billingAPI.cancelSubscription()
      alert('Subscription will be cancelled at the end of the billing period')
      loadBillingData()
    } catch (error) {
      console.error('Error cancelling subscription:', error)
      alert('Failed to cancel subscription')
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const formatCurrency = (amount: number, currency: string = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
    }).format(amount)
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'succeeded':
      case 'paid':
        return 'text-green-600 bg-green-100'
      case 'pending':
      case 'open':
        return 'text-yellow-600 bg-yellow-100'
      case 'failed':
        return 'text-red-600 bg-red-100'
      default:
        return 'text-gray-600 bg-gray-100'
    }
  }

  const pricingTiers = [
    {
      name: 'Free',
      tier: 'free',
      price: 0,
      features: ['30 minutes/month', 'Basic support', '1 voice agent'],
    },
    {
      name: 'Basic',
      tier: 'basic',
      price: 29,
      features: ['1,000 minutes/month', 'Email support', 'Up to 5 agents', 'Basic analytics'],
    },
    {
      name: 'Pro',
      tier: 'pro',
      price: 99,
      features: ['10,000 minutes/month', 'Priority support', 'Unlimited agents', 'Advanced analytics', 'Custom integrations'],
    },
    {
      name: 'Enterprise',
      tier: 'enterprise',
      price: 299,
      features: ['Unlimited minutes', '24/7 support', 'Unlimited agents', 'Custom solutions', 'Dedicated account manager'],
    },
  ]

  return (
    <DashboardLayout>
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Billing & Subscription</h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">Manage your subscription and view billing history</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'overview'
                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('transactions')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'transactions'
                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            Transactions
          </button>
          <button
            onClick={() => setActiveTab('invoices')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'invoices'
                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            Invoices
          </button>
        </nav>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Credit Balance */}
          <div className="bg-gradient-to-r from-orange-400 to-pink-500 dark:from-orange-600 dark:to-pink-700 shadow-lg rounded-lg p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm opacity-90 mb-2">Available Credits</p>
                {loading ? (
                  <div className="h-12 bg-white bg-opacity-20 rounded w-40 animate-pulse"></div>
                ) : (
                  <p className="text-5xl font-bold">
                    ${creditBalance?.balance?.toFixed(2) || '0.00'}
                  </p>
                )}
                <p className="text-sm opacity-75 mt-2">Pay-as-you-go • No monthly fees</p>
              </div>
              <button
                onClick={() => setShowTopUpModal(true)}
                className="px-8 py-3 bg-white dark:bg-gray-900 text-indigo-600 dark:text-indigo-400 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 font-semibold shadow-md transition-all hover:scale-105"
              >
                + Top Up Credits
              </button>
            </div>
          </div>

          {/* Current Subscription (Optional - can be kept for legacy users) */}
          {/* <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Subscription Plan</h2>
            <div className="flex items-center justify-between">
              <div>
                {loading ? (
                  <>
                    <div className="h-9 bg-gray-200 rounded w-32 mb-2 animate-pulse"></div>
                    <div className="h-5 bg-gray-200 rounded w-24 animate-pulse"></div>
                  </>
                ) : (
                  <>
                    <p className="text-3xl font-bold text-gray-700 capitalize">{subscription?.tier || 'Pay-as-you-go'}</p>
                    <p className="text-gray-600 mt-1">
                      {subscription?.active ? 'Active' : 'Credit-based billing'}
                      {subscription?.cancel_at_period_end && ' (Cancels at period end)'}
                    </p>
                  </>
                )}
              </div>
              <button
                onClick={() => setShowUpgradeModal(true)}
                className="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 border border-gray-300"
              >
                {loading ? 'Loading...' : 'View Plans'}
              </button>
            </div>
          </div> */}

          {/* Pricing Plans */}
          {showUpgradeModal && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white rounded-lg p-8 max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-2xl font-bold">Choose Your Plan</h2>
                  <button
                    onClick={() => setShowUpgradeModal(false)}
                    className="text-gray-500 hover:text-gray-700"
                  >
                    ✕
                  </button>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  {pricingTiers.map((tier) => (
                    <div
                      key={tier.tier}
                      className={`border-2 rounded-lg p-6 ${
                        subscription?.tier === tier.tier
                          ? 'border-indigo-600 bg-indigo-50'
                          : 'border-gray-200'
                      }`}
                    >
                      <h3 className="text-xl font-bold mb-2">{tier.name}</h3>
                      <p className="text-3xl font-bold mb-4">
                        ${tier.price}
                        <span className="text-sm text-gray-600">/month</span>
                      </p>
                      <ul className="space-y-2 mb-6">
                        {tier.features.map((feature, idx) => (
                          <li key={idx} className="flex items-start">
                            <span className="text-green-500 mr-2">✓</span>
                            <span className="text-sm">{feature}</span>
                          </li>
                        ))}
                      </ul>
                      <button
                        onClick={() => {
                          setSelectedTier(tier.tier)
                          handleUpgradeSubscription()
                        }}
                        disabled={subscription?.tier === tier.tier}
                        className={`w-full py-2 px-4 rounded-lg ${
                          subscription?.tier === tier.tier
                            ? 'bg-gray-300 cursor-not-allowed'
                            : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                        }`}
                      >
                        {subscription?.tier === tier.tier ? 'Current Plan' : 'Select Plan'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Recent Transactions */}
          <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Recent Transactions</h2>
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="flex items-center justify-between py-3 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex-1">
                      <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-48 mb-2 animate-pulse"></div>
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32 animate-pulse"></div>
                    </div>
                    <div className="text-right">
                      <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-20 mb-2 animate-pulse"></div>
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-16 animate-pulse"></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : transactions.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400">No transactions yet</p>
            ) : (
              <div className="space-y-3">
                {transactions.slice(0, 5).map((transaction) => (
                  <div key={transaction.id} className="flex items-center justify-between py-3 border-b border-gray-200 dark:border-gray-700">
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">{transaction.description || 'Payment'}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">{formatDate(transaction.created_at)}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-gray-900 dark:text-white">{formatCurrency(transaction.amount, transaction.currency)}</p>
                      <span className={`text-xs px-2 py-1 rounded ${getStatusColor(transaction.status)}`}>
                        {transaction.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Transactions Tab */}
      {activeTab === 'transactions' && (
        <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Date</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Description</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Amount</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Method</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-6 py-4"><div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24 animate-pulse"></div></td>
                    <td className="px-6 py-4"><div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32 animate-pulse"></div></td>
                    <td className="px-6 py-4"><div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div></td>
                    <td className="px-6 py-4"><div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div></td>
                    <td className="px-6 py-4"><div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-16 animate-pulse"></div></td>
                  </tr>
                ))
              ) : (
                transactions.map((transaction) => (
                  <tr key={transaction.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                      {formatDate(transaction.created_at)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 dark:text-white">
                      {transaction.description || 'Payment'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                      {formatCurrency(transaction.amount, transaction.currency)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`px-2 py-1 rounded ${getStatusColor(transaction.status)}`}>
                        {transaction.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {transaction.payment_method || '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          {!loading && transactions.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500 dark:text-gray-400">No transactions found</p>
            </div>
          )}
        </div>
      )}

      {/* Invoices Tab */}
      {activeTab === 'invoices' && (
        <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Invoice #</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Period</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Amount</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-6 py-4"><div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-28 animate-pulse"></div></td>
                    <td className="px-6 py-4"><div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-40 animate-pulse"></div></td>
                    <td className="px-6 py-4"><div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div></td>
                    <td className="px-6 py-4"><div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-20 animate-pulse"></div></td>
                    <td className="px-6 py-4"><div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32 animate-pulse"></div></td>
                  </tr>
                ))
              ) : (
                invoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                      {invoice.invoice_number}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                      {formatDate(invoice.period_start)} - {formatDate(invoice.period_end)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                      {formatCurrency(invoice.amount, invoice.currency)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`px-2 py-1 rounded ${getStatusColor(invoice.status)}`}>
                        {invoice.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-indigo-600 dark:text-indigo-400">
                      {invoice.stripe_pdf_url && (
                        <a
                          href={invoice.stripe_pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:underline mr-4"
                        >
                          Download PDF
                        </a>
                      )}
                      {invoice.stripe_invoice_url && (
                        <a
                          href={invoice.stripe_invoice_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:underline"
                        >
                          View
                        </a>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          {!loading && invoices.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500 dark:text-gray-400">No invoices found</p>
            </div>
          )}
        </div>
      )}

      {/* Top Up Credits Modal */}
      {showTopUpModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-8 max-w-md w-full mx-4">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Top Up Credits</h2>
              <button
                onClick={() => setShowTopUpModal(false)}
                className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 text-2xl"
              >
                ✕
              </button>
            </div>
            
            <div className="mb-6">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Current Balance: <span className="font-semibold text-lg text-indigo-600 dark:text-indigo-400">
                  ${creditBalance?.balance?.toFixed(2) || '0.00'}
                </span>
              </p>
              
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Quick Amounts
              </label>
              <div className="grid grid-cols-5 gap-2 mb-4">
                {quickAmounts.map((amount) => (
                  <button
                    key={amount}
                    onClick={() => {
                      setTopUpAmount(amount.toString())
                      setCustomAmount('')
                    }}
                    className={`py-3 rounded-lg font-semibold transition-all ${
                      topUpAmount === amount.toString()
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    ${amount}
                  </button>
                ))}
              </div>
              
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Custom Amount (Min: $5.00)
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400">$</span>
                <input
                  type="number"
                  min="5"
                  step="0.01"
                  value={customAmount}
                  onChange={(e) => {
                    setCustomAmount(e.target.value)
                    setTopUpAmount('')
                  }}
                  placeholder="Enter amount"
                  className="w-full pl-8 pr-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
              
              {(topUpAmount || customAmount) && (
                <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">
                  You will be charged: <span className="font-semibold text-lg text-green-600 dark:text-green-400">
                    ${(parseFloat(topUpAmount || customAmount) || 0).toFixed(2)}
                  </span>
                </p>
              )}
            </div>
            
            <div className="flex gap-3">
              <button
                onClick={() => setShowTopUpModal(false)}
                className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white"
                disabled={processingPayment}
              >
                Cancel
              </button>
              <button
                onClick={handleTopUp}
                disabled={processingPayment || (!topUpAmount && !customAmount)}
                className="flex-1 px-4 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 disabled:cursor-not-allowed font-semibold"
              >
                {processingPayment ? 'Processing...' : 'Continue to Payment'}
              </button>
            </div>
            
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-4 text-center">
              Secure payment powered by Stripe
            </p>
          </div>
        </div>
      )}
    </div>
    </DashboardLayout>
  )
}

export default BillingPage

