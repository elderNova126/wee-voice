import { useState } from 'react'
import { Link } from 'react-router-dom'
import DashboardLayout from '@/layouts/DashboardLayout'
import { supportAPI } from '@/lib/api'
import { Card, CardHeader, CardContent, Button, Input } from '@/components/ui'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'
import { 
  ChatBubbleLeftRightIcon,
  EnvelopeIcon,
  PhoneIcon,
  CheckCircleIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline'

interface TicketForm {
  name: string
  email: string
  subject: string
  message: string
  category: string
}

const categories = [
  { value: 'technical', label: 'Support Technique' },
  { value: 'billing', label: 'Facturation' },
  { value: 'general', label: 'Question Générale' },
  { value: 'feature_request', label: 'Demande de Fonctionnalité' },
  { value: 'bug_report', label: 'Rapport de Bug' },
]

export default function SupportPage() {
  const { user } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [ticketNumber, setTicketNumber] = useState('')
  
  const [formData, setFormData] = useState<TicketForm>({
    name: user?.full_name || '',
    email: user?.email || '',
    subject: '',
    message: '',
    category: 'general'
  })
  
  const [errors, setErrors] = useState<Partial<Record<keyof TicketForm, string>>>({})
  
  const validateForm = (): boolean => {
    const newErrors: Partial<Record<keyof TicketForm, string>> = {}
    
    if (!formData.name.trim()) {
      newErrors.name = 'Le nom est requis'
    }
    
    if (!formData.email.trim()) {
      newErrors.email = 'L\'email est requis'
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Email invalide'
    }
    
    if (!formData.subject.trim()) {
      newErrors.subject = 'Le sujet est requis'
    } else if (formData.subject.length < 5) {
      newErrors.subject = 'Le sujet doit contenir au moins 5 caractères'
    }
    
    if (!formData.message.trim()) {
      newErrors.message = 'Le message est requis'
    } else if (formData.message.length < 10) {
      newErrors.message = 'Le message doit contenir au moins 10 caractères'
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) {
      toast.error('Veuillez corriger les erreurs du formulaire')
      return
    }
    
    setLoading(true)
    try {
      const response = await supportAPI.createTicket(formData)
      setTicketNumber(response.data.ticket_number)
      setSubmitted(true)
      toast.success('Votre demande a été envoyée avec succès!')
    } catch (error: any) {
      console.error('Error submitting ticket:', error)
      toast.error(error.response?.data?.detail || 'Erreur lors de l\'envoi de votre demande')
    } finally {
      setLoading(false)
    }
  }
  
  if (submitted) {
    return (
      <DashboardLayout>
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 mb-6">
              <CheckCircleIcon className="w-12 h-12 text-white" />
            </div>
            <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
              Demande Envoyée!
            </h1>
            <p className="text-xl text-gray-600 dark:text-gray-400">
              Nous avons bien reçu votre demande de support
            </p>
          </div>
          
          <Card className="mb-6">
            <CardContent className="p-8">
              <div className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/30 dark:to-purple-900/30 rounded-xl p-6 border border-indigo-200 dark:border-indigo-800">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Numéro de Ticket
                </h3>
                <p className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600 mb-4">
                  {ticketNumber}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Conservez ce numéro pour suivre votre demande. Un email de confirmation a été envoyé à{' '}
                  <strong>{formData.email}</strong>
                </p>
              </div>
              
              <div className="mt-6 space-y-4">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-500 text-white flex items-center justify-center text-xs font-bold mt-0.5">
                    1
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      Confirmation Envoyée
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Vérifiez votre boîte email pour la confirmation
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-500 text-white flex items-center justify-center text-xs font-bold mt-0.5">
                    2
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      Analyse en Cours
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Notre équipe examine votre demande
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-300 dark:bg-gray-700 text-gray-600 dark:text-gray-400 flex items-center justify-center text-xs font-bold mt-0.5">
                    3
                  </div>
                  <div>
                    <p className="font-medium text-gray-500 dark:text-gray-400">
                      Réponse à Venir
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-500">
                      Nous vous répondrons dans les plus brefs délais
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <div className="flex gap-4">
            <Button
              onClick={() => {
                setSubmitted(false)
                setFormData({
                  name: user?.full_name || '',
                  email: user?.email || '',
                  subject: '',
                  message: '',
                  category: 'general'
                })
              }}
              variant="outline"
              className="flex-1"
            >
              Nouvelle Demande
            </Button>
            <Link to="/dashboard" className="flex-1">
              <Button variant="primary" fullWidth>
                Retour au Tableau de Bord
              </Button>
            </Link>
          </div>
        </div>
      </DashboardLayout>
    )
  }
  
  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Centre de Support
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-400">
            Besoin d'aide? Notre équipe est là pour vous assister.
          </p>
        </div>
        
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Contact Form */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader
                title="Envoyer une Demande"
                subtitle="Remplissez le formulaire ci-dessous et nous vous répondrons dans les plus brefs délais"
                icon={<ChatBubbleLeftRightIcon className="w-6 h-6" />}
              />
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div className="grid md:grid-cols-2 gap-6">
                    <Input
                      label="Nom Complet"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      error={errors.name}
                      required
                      fullWidth
                    />
                    <Input
                      label="Email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      error={errors.email}
                      required
                      fullWidth
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Catégorie <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={formData.category}
                      onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                      className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors duration-200"
                    >
                      {categories.map(cat => (
                        <option key={cat.value} value={cat.value}>
                          {cat.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  
                  <Input
                    label="Sujet"
                    value={formData.subject}
                    onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                    error={errors.subject}
                    required
                    fullWidth
                    helperText="Décrivez brièvement votre problème"
                  />
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Message <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      value={formData.message}
                      onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                      rows={6}
                      className={`w-full px-4 py-2.5 border rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors duration-200 ${
                        errors.message
                          ? 'border-red-500'
                          : 'border-gray-300 dark:border-gray-600'
                      }`}
                      placeholder="Décrivez votre problème en détail..."
                    />
                    {errors.message && (
                      <p className="mt-1.5 text-sm text-red-600 dark:text-red-400">
                        {errors.message}
                      </p>
                    )}
                  </div>
                  
                  <Button
                    type="submit"
                    loading={loading}
                    fullWidth
                    size="lg"
                  >
                    Envoyer la Demande
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
          
          {/* Contact Info & Quick Links */}
          <div className="space-y-6">
            {/* Contact Methods */}
            <Card>
              <CardHeader
                title="Autres Moyens de Contact"
                subtitle="Choisissez votre méthode préférée"
              />
              <CardContent className="space-y-4">
                <div className="flex items-start gap-3 p-4 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-500 flex items-center justify-center">
                    <EnvelopeIcon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">Email</p>
                    <a href="mailto:support@voiceagent.ai" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
                      support@voiceagent.ai
                    </a>
                  </div>
                </div>
                
                <div className="flex items-start gap-3 p-4 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-lg border border-green-200 dark:border-green-800">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-green-500 flex items-center justify-center">
                    <PhoneIcon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">Téléphone</p>
                    <a href="tel:+33123456789" className="text-sm text-green-600 dark:text-green-400 hover:underline">
                      +33 1 23 45 67 89
                    </a>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Lun-Ven: 9h-18h
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Tips */}
            <Card className="bg-gradient-to-br from-yellow-50 to-orange-50 dark:from-yellow-900/20 dark:to-orange-900/20 border-yellow-200 dark:border-yellow-800">
              <CardContent className="p-6">
                <div className="flex items-start gap-3 mb-4">
                  <ExclamationCircleIcon className="w-6 h-6 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                      Conseils pour une Réponse Rapide
                    </h3>
                    <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
                      <li>• Soyez précis dans votre description</li>
                      <li>• Incluez des captures d'écran si possible</li>
                      <li>• Mentionnez les étapes pour reproduire le problème</li>
                      <li>• Indiquez votre navigateur et système d'exploitation</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

