import React, { useState, useEffect } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import DashboardLayout from '../layouts/DashboardLayout';
import api from '../lib/api';
import { useTranslation } from '../lib/translations';
import { useLanguageStore } from '../store/languageStore';
import toast from 'react-hot-toast';
import {
  PhoneIcon,
  CloudArrowUpIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  Cog6ToothIcon,
  PlusCircleIcon,
  TrashIcon,
  PlayCircleIcon,
} from '@heroicons/react/24/outline'

interface PhoneNumber {
  id: number;
  phone_number: string;
  country_code: string;
  status: string;
  business_name: string;
  monthly_cost: string;
  per_minute_cost: string;
  agent_id: number | null;
  created_at: string;
  activated_at: string | null;
  zadarma_number_id?: string | null;
  pbx_enabled?: boolean;
  pbx_extension?: string | null;
  pbx_scenario_id?: string | null;
  business_hours?: PBXBusinessHours | null;
  menu_options?: StoredPBXMenuOption[] | null;
  after_hours_routing?: StoredAfterHoursRouting | null;
}

interface Agent {
  id: number;
  name: string;
  description: string;
  status: string;
}

interface VerificationDocument {
  id: number;
  document_type: string;
  document_name: string;
  status: string;
  rejection_reason: string | null;
  created_at: string;
}

type DayCode = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';

interface PBXBusinessHours {
  timezone: string;
  open_time: string;
  close_time: string;
  days: DayCode[];
}

interface PBXMenuOption {
  key: string;
  label?: string;
  destination_type: 'agent' | 'forward' | 'voicemail' | 'external';
  destination_value?: string;
}

interface StoredPBXMenuOption extends PBXMenuOption {
  destination?: {
    type?: string;
    value?: string;
  };
}

interface AfterHoursRouting {
  destination_type: 'agent' | 'forward' | 'voicemail' | 'external';
  destination_value?: string;
  message?: string;
}

interface StoredAfterHoursRouting extends AfterHoursRouting {
  destination?: {
    type?: string;
    value?: string;
  };
}

interface PBXFormState {
  business_hours: PBXBusinessHours;
  menu_options: PBXMenuOption[];
  after_hours_routing: AfterHoursRouting;
}

export const PhoneNumbersPage: React.FC = () => {
  const t = useTranslation();
  
  // Safety check: ensure phoneNumbers translations exist
  if (!t?.phoneNumbers) {
    console.error('phoneNumbers translations not found', {
      hasT: !!t,
      availableKeys: t ? Object.keys(t) : [],
      language: useLanguageStore.getState().language,
      translationKeys: t?.phoneNumbers ? Object.keys(t.phoneNumbers) : []
    });
  }
  
  const [phoneNumbers, setPhoneNumbers] = useState<PhoneNumber[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedNumber, setSelectedNumber] = useState<PhoneNumber | null>(null);
  const [documents, setDocuments] = useState<VerificationDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [requestLoading, setRequestLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [showRequestModal, setShowRequestModal] = useState(false);
  const [showAddExistingModal, setShowAddExistingModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showAssignAgentModal, setShowAssignAgentModal] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [showPBXModal, setShowPBXModal] = useState(false);
  const [pbxTargetNumber, setPbxTargetNumber] = useState<PhoneNumber | null>(null);

  // Form states
  const [formData, setFormData] = useState({
    phone_number: '',
    country_code: 'FR',
    business_name: '',
    business_type: 'company',
    business_address: ''
  });

  const [existingNumberData, setExistingNumberData] = useState({
    phone_number: '',
    country_code: 'BE',
    business_name: ''
  });

  const [uploadData, setUploadData] = useState({
    document_type: 'company_registration',
    file: null as File | null
  });

  const defaultBusinessHours: PBXBusinessHours = {
    timezone: 'Europe/Paris',
    open_time: '09:00',
    close_time: '18:00',
    days: ['mon', 'tue', 'wed', 'thu', 'fri'],
  };

  const getDefaultPBXForm = (): PBXFormState => {
    const isFrench = t.common.status === 'Statut';
    return {
      business_hours: { ...defaultBusinessHours },
      menu_options: [
        {
          key: '1',
          label: isFrench ? 'Parler avec notre agent IA' : 'Speak with our AI agent',
          destination_type: 'agent',
          destination_value: '',
        },
      ],
      after_hours_routing: {
        destination_type: 'agent',
        message: isFrench ? 'Nos bureaux sont actuellement fermés. Connexion à notre agent virtuel.' : 'Our offices are currently closed. Connecting you to our virtual agent.',
        destination_value: '',
      },
    };
  };

  const [pbxForm, setPbxForm] = useState<PBXFormState>(getDefaultPBXForm());
  const [pbxSaving, setPbxSaving] = useState(false);

  const dayOptions: { value: DayCode; label: string }[] = [
    { value: 'mon', label: 'Mon' },
    { value: 'tue', label: 'Tue' },
    { value: 'wed', label: 'Wed' },
    { value: 'thu', label: 'Thu' },
    { value: 'fri', label: 'Fri' },
    { value: 'sat', label: 'Sat' },
    { value: 'sun', label: 'Sun' },
  ];

  const timezoneOptions = [
    'Europe/Paris',
    'Europe/Brussels',
    'Europe/London',
    'America/New_York',
    'America/Los_Angeles',
    'UTC',
  ];

  const formatBusinessHoursSummary = (hours?: PBXBusinessHours | null) => {
    if (!hours) return t?.phoneNumbers?.notConfigured || 'Not configured';
    const activeDays = Array.isArray(hours.days)
      ? dayOptions.filter((d) => (hours.days as DayCode[]).includes(d.value))
      : [];
    const orderedDays = activeDays
      .map((d) => d.label)
      .join(', ');

    const openTime = hours.open_time || defaultBusinessHours.open_time;
    const closeTime = hours.close_time || defaultBusinessHours.close_time;
    const timezone = hours.timezone || defaultBusinessHours.timezone;
    return `${orderedDays || (t.common.status === 'Statut' ? 'Aucun jour sélectionné' : 'No days selected')} • ${openTime} - ${closeTime} (${timezone})`;
  };

  const describeAfterHoursDestination = (afterHours?: StoredAfterHoursRouting | null) => {
    if (!afterHours) {
      return t.common.status === 'Statut' ? 'Par défaut : se connecter à l\'agent IA' : 'Default: connect to AI agent';
    }

    const destinationType = afterHours.destination_type || afterHours.destination?.type || 'agent';
    if (destinationType === 'agent') {
      return t?.phoneNumbers?.connectToAIAgent || 'Connect to AI Agent';
    }
    if (destinationType === 'voicemail') {
      return t?.phoneNumbers?.sendToVoicemail || 'Send to Voicemail';
    }
    if (destinationType === 'forward') {
      return `${t?.phoneNumbers?.forwardTo || 'Forward to'} ${afterHours.destination_value || afterHours.destination?.value || (t?.phoneNumbers?.externalNumber || 'External Number')}`;
    }
    if (destinationType === 'external') {
      return `${t?.phoneNumbers?.externalDestination || 'External Destination'} ${afterHours.destination_value || afterHours.destination?.value || 'N/A'}`;
    }
    return t?.phoneNumbers?.customRouting || 'Custom Routing';
  };

  const initializePBXFormFromNumber = (number: PhoneNumber): PBXFormState => {
    const form = getDefaultPBXForm();

    if (number.business_hours) {
      const incomingDays = Array.isArray(number.business_hours.days)
        ? number.business_hours.days.filter((day: any): day is DayCode =>
            dayOptions.some((opt) => opt.value === day)
          )
        : form.business_hours.days;

      form.business_hours = {
        timezone: number.business_hours.timezone || form.business_hours.timezone,
        open_time: number.business_hours.open_time || form.business_hours.open_time,
        close_time: number.business_hours.close_time || form.business_hours.close_time,
        days: incomingDays.length ? incomingDays : form.business_hours.days,
      };
    }

    if (number.menu_options && number.menu_options.length > 0) {
      form.menu_options = number.menu_options.map((option) => {
        const destinationType =
          (option.destination_type ||
            option.destination?.type ||
            'agent') as PBXMenuOption['destination_type'];
        return {
          key: option.key ?? '',
          label: option.label ?? '',
          destination_type: destinationType,
          destination_value:
            destinationType === 'agent'
              ? ''
              : option.destination_value ?? option.destination?.value ?? '',
        };
      });
    }

    if (number.after_hours_routing) {
      const destinationType =
        (number.after_hours_routing.destination_type ||
          number.after_hours_routing.destination?.type ||
          'agent') as AfterHoursRouting['destination_type'];

      form.after_hours_routing = {
        destination_type: destinationType,
        destination_value:
          destinationType === 'agent'
            ? ''
            : number.after_hours_routing.destination_value ??
              number.after_hours_routing.destination?.value ??
              '',
        message:
          number.after_hours_routing.message ??
          form.after_hours_routing.message,
      };
    }

    return form;
  };

  const openPBXModal = (number: PhoneNumber) => {
    if (!number.agent_id) {
      toast.error(t.common.status === 'Statut' ? 'Assignez ce numéro de téléphone à un agent avant de configurer le routage PBX.' : 'Assign this phone number to an agent before configuring PBX routing.');
      return;
    }
    const preparedForm = initializePBXFormFromNumber(number);
    setPbxForm(preparedForm);
    setPbxTargetNumber(number);
    setShowPBXModal(true);
  };

  const closePBXModal = () => {
    setShowPBXModal(false);
    setPbxTargetNumber(null);
    setPbxForm(getDefaultPBXForm());
    setPbxSaving(false);
  };

  const toggleBusinessDay = (day: DayCode) => {
    setPbxForm((prev) => {
      const days = prev.business_hours.days.includes(day)
        ? prev.business_hours.days.filter((d) => d !== day)
        : [...prev.business_hours.days, day];
      return {
        ...prev,
        business_hours: {
          ...prev.business_hours,
          days,
        },
      };
    });
  };

  const updateBusinessHours = (field: 'timezone' | 'open_time' | 'close_time', value: string) => {
    setPbxForm((prev) => ({
      ...prev,
      business_hours: {
        ...prev.business_hours,
        [field]: value,
      },
    }));
  };

  const updateMenuOption = (index: number, field: keyof PBXMenuOption, value: string) => {
    setPbxForm((prev) => {
      const next = [...prev.menu_options];
      const updated: PBXMenuOption = {
        ...next[index],
        [field]: value,
      } as PBXMenuOption;

      if (field === 'destination_type' && value === 'agent') {
        updated.destination_value = '';
      }
      next[index] = updated;
      return {
        ...prev,
        menu_options: next,
      };
    });
  };

  const addMenuOption = () => {
    setPbxForm((prev) => ({
      ...prev,
      menu_options: [
        ...prev.menu_options,
        {
          key: '',
          label: '',
          destination_type: 'agent',
          destination_value: '',
        },
      ],
    }));
  };

  const removeMenuOption = (index: number) => {
    setPbxForm((prev) => {
      if (prev.menu_options.length <= 1) {
        return prev;
      }
      const next = prev.menu_options.filter((_, i) => i !== index);
      return {
        ...prev,
        menu_options: next,
      };
    });
  };

  const updateAfterHours = (field: keyof AfterHoursRouting, value: string) => {
    setPbxForm((prev) => {
      const next: AfterHoursRouting = {
        ...prev.after_hours_routing,
        [field]: value,
      };
      if (field === 'destination_type' && value === 'agent') {
        next.destination_value = '';
      }
      return {
        ...prev,
        after_hours_routing: next,
      };
    });
  };

  const handleSavePBX = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!pbxTargetNumber) return;

    setPbxSaving(true);

    const selectedDays = pbxForm.business_hours.days.filter((day): day is DayCode =>
      dayOptions.some((opt) => opt.value === day)
    );

    if (selectedDays.length === 0) {
      toast.error(t.common.status === 'Statut' ? 'Sélectionnez au moins un jour ouvrable pour le menu PBX.' : 'Select at least one business day for the PBX menu.');
      setPbxSaving(false);
      return;
    }

    const menuOptionsPayload = pbxForm.menu_options
      .filter((option) => option.key.trim().length > 0)
      .map((option) => {
        const destinationType = option.destination_type;
        const payloadOption: Record<string, string> = {
          key: option.key.trim(),
          destination_type: destinationType,
        };
        if (option.label && option.label.trim()) {
          payloadOption.label = option.label.trim();
        }
        if (destinationType !== 'agent') {
          payloadOption.destination_value = (option.destination_value || '').trim();
        }
        return payloadOption;
      });

    const afterHoursType = pbxForm.after_hours_routing.destination_type;
    const afterHoursPayload: Record<string, string> = {
      destination_type: afterHoursType,
    };
    if (pbxForm.after_hours_routing.message) {
      afterHoursPayload.message = pbxForm.after_hours_routing.message;
    }
    if (afterHoursType !== 'agent') {
      afterHoursPayload.destination_value = (pbxForm.after_hours_routing.destination_value || '').trim();
    }

    const payload: Record<string, any> = {
      business_hours: {
        ...pbxForm.business_hours,
        days: selectedDays,
      },
      after_hours_routing: afterHoursPayload,
    };

    if (menuOptionsPayload.length > 0) {
      payload.menu_options = menuOptionsPayload;
    }

    try {
      await api.post(`/phone-numbers/${pbxTargetNumber.id}/configure-pbx`, payload);
      await loadPhoneNumbers();
      toast.success(t.phoneNumbers.pbxSavedSuccess);
      closePBXModal();
    } catch (error: any) {
      console.error('Error saving PBX configuration:', error);
      toast.error(t.phoneNumbers.updateError + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setPbxSaving(false);
    }
  };

  useEffect(() => {
    loadPhoneNumbers();
    loadAgents();
  }, []);

  const loadPhoneNumbers = async () => {
    try {
      const response = await api.get('/phone-numbers/');
      setPhoneNumbers(response.data);
    } catch (error) {
      console.error('Error loading phone numbers:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAgents = async () => {
    try {
      const response = await api.get('/agents/');
      setAgents(response.data);
    } catch (error) {
      console.error('Error loading agents:', error);
    }
  };

  const loadDocuments = async (phoneNumberId: number) => {
    setDocumentsLoading(true);
    try {
      const response = await api.get(`/phone-numbers/${phoneNumberId}/documents`);
      setDocuments(response.data);
    } catch (error) {
      console.error('Error loading documents:', error);
    } finally {
      setDocumentsLoading(false);
    }
  };

  const handleAddExistingNumber = async (e: React.FormEvent) => {
    e.preventDefault();
    setRequestLoading(true);
    try {
      await api.post('/phone-numbers/add-existing', existingNumberData);
      await loadPhoneNumbers();
      setShowAddExistingModal(false);
      setExistingNumberData({
        phone_number: '',
        country_code: 'BE',
        business_name: ''
      });
      toast.success(t.phoneNumbers.phoneNumberAddedSuccess);
    } catch (error: any) {
      toast.error(t.phoneNumbers.createError + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setRequestLoading(false);
    }
  };

  const handleRequestNumber = async (e: React.FormEvent) => {
    e.preventDefault();
    setRequestLoading(true);
    try {
      await api.post('/phone-numbers/request', formData);
      await loadPhoneNumbers();
      setShowRequestModal(false);
      setFormData({
        phone_number: '',
        country_code: 'FR',
        business_name: '',
        business_type: 'company',
        business_address: ''
      });
      toast.success(t.phoneNumbers.phoneNumberRequestedSuccess);
    } catch (error: any) {
      toast.error(t.phoneNumbers.createError + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setRequestLoading(false);
    }
  };

  const handleUploadDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedNumber || !uploadData.file) return;

    setUploadLoading(true);
    const formDataToSend = new FormData();
    formDataToSend.append('document_type', uploadData.document_type);
    formDataToSend.append('file', uploadData.file);

    try {
      await api.post(
        `/phone-numbers/${selectedNumber.id}/upload-document`,
        formDataToSend,
        {
          headers: { 'Content-Type': 'multipart/form-data' }
        }
      );
      await loadDocuments(selectedNumber.id);
      setShowUploadModal(false);
      setUploadData({ document_type: 'company_registration', file: null });
      toast.success(t.phoneNumbers.documentUploadedSuccess);
    } catch (error: any) {
      toast.error(t.common.error + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setUploadLoading(false);
    }
  };

  const handleAssignAgent = async () => {
    if (!selectedNumber || !selectedAgentId) return;

    setRequestLoading(true);
    try {
      await api.post(`/phone-numbers/${selectedNumber.id}/activate/${selectedAgentId}`);
      await loadPhoneNumbers();
      setShowAssignAgentModal(false);
      setSelectedNumber(null);
      setSelectedAgentId(null);
      toast.success(t.phoneNumbers.agentAssignedSuccess);
    } catch (error: any) {
      toast.error(t.phoneNumbers.updateError + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setRequestLoading(false);
    }
  };

  const getAgentName = (agentId: number | null) => {
    if (!agentId) return t.common.status === 'Statut' ? 'Non assigné' : 'Not assigned';
    const agent = agents.find(a => a.id === agentId);
    return agent ? agent.name : (t?.phoneNumbers?.unknownAgent || 'Unknown Agent');
  };

  const handleTestCall = async (number: PhoneNumber) => {
    try {
      const response = await api.post(
        `/zadarma/test-call?phone_number=${encodeURIComponent(number.phone_number)}&caller_id=${encodeURIComponent('+33123456789')}`
      );

      toast.success(
        t?.phoneNumbers?.testCallSuccess ||
        `Test call simulated! Call ID: ${response.data.call.id}. The call will progress through: initiated → in_progress → completed over 5 seconds. Navigate to the Calls page to see real-time updates.`
      );

      // Optionally reload phone numbers to show updated status
      await loadPhoneNumbers();
    } catch (error: any) {
      toast.error(
        t?.phoneNumbers?.testCallError ||
        'Failed to simulate test call: ' + (error.response?.data?.detail || error.message)
      );
    }
  };

  const getStatusBadge = (status: string) => {
    const statusColors: Record<string, string> = {
      pending: 'bg-gray-500',
      documents_submitted: 'bg-blue-500',
      under_review: 'bg-yellow-500',
      approved: 'bg-green-500',
      rejected: 'bg-red-500',
      active: 'bg-emerald-600',
      suspended: 'bg-orange-500',
      cancelled: 'bg-gray-600'
    };

    return (
      <Badge className={statusColors[status] || 'bg-gray-500'}>
        {status.replace('_', ' ').toUpperCase()}
      </Badge>
    );
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'accepted':
        return <CheckCircleIcon className="text-green-600 h-5 w-5" />;
      case 'rejected':
        return <XCircleIcon className="text-red-600 h-5 w-5" />;
      case 'in_review':
        return <ClockIcon className="text-yellow-600 h-5 w-5" />;
      default:
        return <ExclamationTriangleIcon className="text-gray-600 h-5 w-5" />;
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          {/* Header - Keep static */}
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t?.phoneNumbers?.title || 'Phone Numbers'}</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                {t?.phoneNumbers?.subtitle || 'Manage phone numbers for your voice agents'}
              </p>
            </div>
            <Button disabled>
              <PhoneIcon className="mr-2 h-4 w-4" />
              {t?.phoneNumbers?.requestNewNumber || 'Request New Number'}
            </Button>
          </div>

          {/* Loading skeleton for phone numbers */}
          <div className="grid gap-6">
            {[1, 2, 3].map((i) => (
              <Card key={i}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse">
                      <div className="w-6 h-6 bg-gray-300 dark:bg-gray-600 rounded"></div>
                    </div>
                    <div className="space-y-2">
                      <div className="h-6 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
                      <div className="h-4 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
                      <div className="h-4 w-40 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
                    </div>
                  </div>
                  <div className="text-right space-y-2">
                    <div className="h-6 w-20 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse"></div>
                    <div className="h-8 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t?.phoneNumbers?.title || 'Phone Numbers'}</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {t?.phoneNumbers?.subtitle || 'Manage phone numbers for your voice agents'}
          </p>
        </div>
        <div className="flex gap-3">
          <Button 
            onClick={() => setShowAddExistingModal(true)}
          >
            <PhoneIcon className="h-4 w-4 mr-2" />
            {t?.phoneNumbers?.addExistingNumber || 'Add Existing Number'}
          </Button>
          <Button onClick={() => setShowRequestModal(true)} variant="outline">
            {t?.phoneNumbers?.requestNewNumber || 'Request New Number'}
          </Button>
        </div>
      </div>

      {/* Phone Numbers List */}
      {phoneNumbers.length === 0 ? (
        <Card>
            <div className="text-center py-12">
              <PhoneIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
                {t?.phoneNumbers?.noPhoneNumbers || 'No Phone Numbers'}
              </h3>
              <p className="mt-2 text-gray-600 dark:text-gray-400">
                {t?.phoneNumbers?.noPhoneNumbersDesc || 'Add your existing Zadarma number or request a new one'}
              </p>
              <div className="flex gap-3 justify-center mt-4">
                <Button onClick={() => setShowAddExistingModal(true)}>
                  {t?.phoneNumbers?.addExistingNumber || 'Add Existing Number'}
                </Button>
                <Button onClick={() => setShowRequestModal(true)} variant="outline">
                  {t?.phoneNumbers?.requestNewNumber || 'Request New Number'}
                </Button>
              </div>
            </div>
        </Card>
      ) : (
        <div className="grid gap-6">
          {phoneNumbers.map((number) => (
            <Card key={number.id}>
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-4">
                  <div className="p-3 bg-indigo-100 dark:bg-indigo-900 rounded-lg">
                    <PhoneIcon className="text-indigo-600 dark:text-indigo-400 h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {number.phone_number}
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {number.business_name} • {number.country_code}
                    </p>
                    <div className="flex items-center gap-4 mt-2 text-sm">
                      <span className="text-gray-500">{t?.phoneNumbers?.monthly || 'Monthly'} ${number.monthly_cost}</span>
                      <span className="text-gray-500">{t?.phoneNumbers?.perMinute || 'Per minute'} ${number.per_minute_cost}</span>
                    </div>
                    <div className="mt-2 text-sm">
                      <span className="text-gray-700 dark:text-gray-300 font-medium">{t?.phoneNumbers?.agent || 'Agent'}: </span>
                      <span className={number.agent_id ? "text-green-600 dark:text-green-400 font-medium" : "text-orange-600 dark:text-orange-400"}>
                        {getAgentName(number.agent_id)}
                      </span>
                    </div>
                    <div className="mt-3 text-sm">
                      <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">
                        {t?.phoneNumbers?.pbxRouting || 'PBX Routing'}
                      </div>
                      {number.pbx_enabled ? (
                        <div className="space-y-1 text-gray-700 dark:text-gray-300">
                          <div>
                            <span className="font-medium">{t?.phoneNumbers?.extension || 'Extension'}</span>{' '}
                            {number.pbx_extension || (t?.phoneNumbers?.auto || 'Auto')}
                          </div>
                          <div>
                            <span className="font-medium">{t?.phoneNumbers?.businessHours || 'Business Hours'}</span>{' '}
                            {formatBusinessHoursSummary(number.business_hours || null)}
                          </div>
                          <div>
                            <span className="font-medium">{t?.phoneNumbers?.afterHours || 'After Hours'}</span>{' '}
                            {describeAfterHoursDestination(number.after_hours_routing || null)}
                          </div>
                        </div>
                      ) : (
                        <p className="text-gray-500 dark:text-gray-400">
                          {t?.phoneNumbers?.pbxNotConfiguredDesc || 'PBX routing not configured'}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
                <div className="text-right space-y-2">
                  {getStatusBadge(number.status)}
                  <div className="flex flex-col gap-2">
                    {number.status === 'pending' || number.status === 'documents_submitted' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedNumber(number);
                          loadDocuments(number.id);
                          setShowUploadModal(true);
                        }}
                      >
                        <CloudArrowUpIcon className="mr-2 h-3.5 w-3.5" />
                        {t?.phoneNumbers?.uploadDocuments || 'Upload Documents'}
                      </Button>
                    ) : null}
                    {(number.status === 'active' || number.status === 'approved') && (
                      <Button
                        size="sm"
                        onClick={() => {
                          setSelectedNumber(number);
                          setSelectedAgentId(number.agent_id);
                          setShowAssignAgentModal(true);
                        }}
                      >
                        {number.agent_id ? (t?.phoneNumbers?.changeAgent || 'Change Agent') : (t?.phoneNumbers?.assignAgent || 'Assign Agent')}
                      </Button>
                    )}
                    {number.agent_id && number.zadarma_number_id && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => openPBXModal(number)}
                      >
                        <Cog6ToothIcon className="mr-2 h-3.5 w-3.5" />
                        {t?.phoneNumbers?.configurePBX || 'Configure PBX'}
                      </Button>
                    )}
                    {number.agent_id && !number.zadarma_number_id && (
                      <div className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                        {t?.phoneNumbers?.pbxRequiresZadarma || 'PBX configuration requires Zadarma number'}
                      </div>
                    )}
                    {number.agent_id && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleTestCall(number)}
                      >
                        <PlayCircleIcon className="mr-2 h-3.5 w-3.5" />
                        {t?.phoneNumbers?.testCall || 'Test Call'}
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              {/* Show uploaded documents */}
              {selectedNumber?.id === number.id && (
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                    {t?.phoneNumbers?.verificationDocuments || 'Verification Documents'}
                  </h4>
                  {documentsLoading ? (
                    <div className="space-y-2">
                      {[1, 2].map((i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg animate-pulse"
                        >
                          <div className="flex items-center space-x-3">
                            <div className="w-5 h-5 bg-gray-300 dark:bg-gray-600 rounded-full"></div>
                            <div className="space-y-1">
                              <div className="h-4 w-32 bg-gray-300 dark:bg-gray-600 rounded"></div>
                              <div className="h-3 w-24 bg-gray-300 dark:bg-gray-600 rounded"></div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="h-6 w-16 bg-gray-300 dark:bg-gray-600 rounded-full"></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : documents.length > 0 ? (
                    <div className="space-y-2">
                      {documents.map((doc) => (
                        <div
                          key={doc.id}
                          className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
                        >
                          <div className="flex items-center space-x-3">
                            {getStatusIcon(doc.status)}
                            <div>
                              <p className="text-sm font-medium text-gray-900 dark:text-white">
                                {doc.document_name}
                              </p>
                              <p className="text-xs text-gray-500">
                                {doc.document_type.replace('_', ' ')}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <Badge
                              className={
                                doc.status === 'accepted'
                                  ? 'bg-green-500'
                                  : doc.status === 'rejected'
                                  ? 'bg-red-500'
                                  : 'bg-yellow-500'
                              }
                            >
                              {doc.status}
                            </Badge>
                            {doc.rejection_reason && (
                              <p className="text-xs text-red-600 mt-1">{doc.rejection_reason}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 dark:text-gray-400">{t?.phoneNumbers?.noDocumentsUploaded || 'No documents uploaded'}</p>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Add Existing Number Modal */}
      {showAddExistingModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-lg w-full">
            <h2 className="text-2xl font-bold mb-4">{t?.phoneNumbers?.addExistingPhoneNumber || 'Add Existing Phone Number'}</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              {t?.phoneNumbers?.addExistingDesc || 'Add your existing Zadarma phone number to your account'}
            </p>
            <form onSubmit={handleAddExistingNumber} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.phoneNumberLabel || 'Phone Number'}</label>
                <input
                  type="text"
                  required
                  value={existingNumberData.phone_number}
                  onChange={(e) => setExistingNumberData({ ...existingNumberData, phone_number: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  placeholder={t?.phoneNumbers?.phoneNumberPlaceholder || 'Enter phone number'}
                />
                <p className="text-xs text-gray-500 mt-1">
                  {t?.phoneNumbers?.phoneNumberHelper || 'Enter your Zadarma phone number'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.countryCode || 'Country Code'}</label>
                <select
                  value={existingNumberData.country_code}
                  onChange={(e) => setExistingNumberData({ ...existingNumberData, country_code: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                >
                  <option value="BE">{t.common.status === 'Statut' ? 'Belgique (BE)' : 'Belgium (BE)'}</option>
                  <option value="FR">{t.common.status === 'Statut' ? 'France (FR)' : 'France (FR)'}</option>
                  <option value="US">{t.common.status === 'Statut' ? 'États-Unis (US)' : 'United States (US)'}</option>
                  <option value="UK">{t.common.status === 'Statut' ? 'Royaume-Uni (UK)' : 'United Kingdom (UK)'}</option>
                  <option value="DE">{t.common.status === 'Statut' ? 'Allemagne (DE)' : 'Germany (DE)'}</option>
                  <option value="NL">{t.common.status === 'Statut' ? 'Pays-Bas (NL)' : 'Netherlands (NL)'}</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.businessNameOptional || 'Business Name (Optional)'}</label>
                <input
                  type="text"
                  value={existingNumberData.business_name}
                  onChange={(e) => setExistingNumberData({ ...existingNumberData, business_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  placeholder={t?.phoneNumbers?.businessNamePlaceholder || 'Enter business name'}
                />
              </div>

              <div className="flex gap-3 pt-4">
                <Button type="submit" className="flex-1" disabled={requestLoading}>
                  {requestLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      {t?.phoneNumbers?.adding || 'Adding...'}
                    </>
                  ) : (
                    t?.phoneNumbers?.addPhoneNumberButton || 'Add Phone Number'
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowAddExistingModal(false)}
                  className="flex-1"
                >
                  {t?.common?.cancel || 'Cancel'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Request Number Modal */}
      {showRequestModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-4">{t?.phoneNumbers?.requestNewPhoneNumber || 'Request New Phone Number'}</h2>
            <form onSubmit={handleRequestNumber} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.phoneNumber || 'Phone Number'}</label>
                <input
                  type="text"
                  required
                  value={formData.phone_number}
                  onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  placeholder={t?.phoneNumbers?.phoneNumberPlaceholderRequest || 'Enter desired phone number'}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.countryCode || 'Country Code'}</label>
                <select
                  value={formData.country_code}
                  onChange={(e) => setFormData({ ...formData, country_code: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                >
                  <option value="FR">{t.common.status === 'Statut' ? 'France (FR)' : 'France (FR)'}</option>
                  <option value="US">{t.common.status === 'Statut' ? 'États-Unis (US)' : 'United States (US)'}</option>
                  <option value="UK">{t.common.status === 'Statut' ? 'Royaume-Uni (UK)' : 'United Kingdom (UK)'}</option>
                  <option value="DE">{t.common.status === 'Statut' ? 'Allemagne (DE)' : 'Germany (DE)'}</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.businessType || 'Business Type'}</label>
                <select
                  value={formData.business_type}
                  onChange={(e) => setFormData({ ...formData, business_type: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                >
                  <option value="company">{t?.phoneNumbers?.company || 'Company'}</option>
                  <option value="individual">{t?.phoneNumbers?.individual || 'Individual'}</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.businessName || 'Business Name'}</label>
                <input
                  type="text"
                  required
                  value={formData.business_name}
                  onChange={(e) => setFormData({ ...formData, business_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.businessAddress || 'Business Address'}</label>
                <textarea
                  required
                  value={formData.business_address}
                  onChange={(e) => setFormData({ ...formData, business_address: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  rows={3}
                />
              </div>

              <div className="flex gap-3 pt-4">
                <Button type="submit" className="flex-1" disabled={requestLoading}>
                  {requestLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      {t?.phoneNumbers?.requesting || 'Requesting...'}
                    </>
                  ) : (
                    t?.phoneNumbers?.requestNewNumber || 'Request New Number'
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowRequestModal(false)}
                  className="flex-1"
                >
                  {t?.common?.cancel || 'Cancel'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Assign Agent Modal */}
      {showAssignAgentModal && selectedNumber && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-lg w-full">
            <h2 className="text-2xl font-bold mb-4">{t?.phoneNumbers?.assignAgentToPhoneNumber || 'Assign Agent to Phone Number'}</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              {t?.phoneNumbers?.chooseAgentDescription || 'Choose an agent to handle calls for'} <strong>{selectedNumber.phone_number}</strong>
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.selectAnAgent || 'Select an Agent'}</label>
                {agents.length === 0 ? (
                  <div className="text-center py-8 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <p className="text-gray-500">{t?.phoneNumbers?.noAgentsAvailable || 'No agents available'}</p>
                    <p className="text-sm text-gray-400 mt-2">{t?.phoneNumbers?.createAgentFirst || 'Create an agent first'}</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {agents.map((agent) => (
                      <div
                        key={agent.id}
                        onClick={() => setSelectedAgentId(agent.id)}
                        className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
                          selectedAgentId === agent.id
                            ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-900/20'
                            : 'border-gray-200 dark:border-gray-700 hover:border-indigo-400'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className="font-semibold text-gray-900 dark:text-white">{agent.name}</h4>
                            <p className="text-sm text-gray-600 dark:text-gray-400">{agent.description}</p>
                          </div>
                          {selectedAgentId === agent.id && (
                            <CheckCircleIcon className="h-6 w-6 text-indigo-600" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex gap-3 pt-4">
                <Button
                  onClick={handleAssignAgent}
                  className="flex-1"
                  disabled={!selectedAgentId || requestLoading}
                >
                  {requestLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      {t?.phoneNumbers?.assigning || 'Assigning...'}
                    </>
                  ) : (
                    t?.phoneNumbers?.assignAgentButton || 'Assign Agent'
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowAssignAgentModal(false);
                    setSelectedNumber(null);
                    setSelectedAgentId(null);
                  }}
                  className="flex-1"
                >
                  {t?.common?.cancel || 'Cancel'}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Upload Document Modal */}
      {showUploadModal && selectedNumber && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-lg w-full">
            <h2 className="text-2xl font-bold mb-4">{t.phoneNumbers.uploadVerificationDocument}</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              {t.phoneNumbers.uploadDocumentsFor} {selectedNumber.phone_number}
            </p>
            <form onSubmit={handleUploadDocument} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">{t.phoneNumbers.documentType}</label>
                <select
                  value={uploadData.document_type}
                  onChange={(e) => setUploadData({ ...uploadData, document_type: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                >
                  <option value="company_registration">{t.common.status === 'Statut' ? 'Enregistrement d\'entreprise' : 'Company Registration'}</option>
                  <option value="proof_of_address">{t.common.status === 'Statut' ? 'Justificatif de domicile' : 'Proof of Address'}</option>
                  <option value="passport">{t.common.status === 'Statut' ? 'Passeport' : 'Passport'}</option>
                  <option value="national_id">{t.common.status === 'Statut' ? 'Carte d\'identité nationale' : 'National ID'}</option>
                  <option value="other">{t.common.status === 'Statut' ? 'Autre' : 'Other'}</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.file || 'File'}</label>
                <input
                  type="file"
                  required
                  onChange={(e) =>
                    setUploadData({ ...uploadData, file: e.target.files?.[0] || null })
                  }
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  accept=".pdf,.jpg,.jpeg,.png"
                />
                <p className="text-xs text-gray-500 mt-1">
                  {t.common.status === 'Statut' ? 'Formats acceptés : PDF, JPG, PNG (max 10 Mo)' : 'Accepted formats: PDF, JPG, PNG (max 10MB)'}
                </p>
              </div>

              <div className="flex gap-3 pt-4">
                <Button type="submit" className="flex-1" disabled={uploadLoading}>
                  {uploadLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      {t?.phoneNumbers?.uploading || 'Uploading...'}
                    </>
                  ) : (
                    <>
                      <CloudArrowUpIcon className="mr-2 h-4 w-4" />
                      {t?.phoneNumbers?.uploadDocumentButton || 'Upload Document'}
                    </>
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowUploadModal(false);
                    setSelectedNumber(null);
                  }}
                  className="flex-1"
                >
                  {t?.common?.cancel || 'Cancel'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* PBX Configuration Modal */}
      {showPBXModal && pbxTargetNumber && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 px-4">
          <Card className="max-w-3xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-2">{t?.phoneNumbers?.pbxConfiguration || 'PBX Configuration'}</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              {t.common.status === 'Statut' ? 'Définissez les heures d\'ouverture et les options IVR pour' : 'Define business hours and IVR options for'} <strong>{pbxTargetNumber.phone_number}</strong>. {t.common.status === 'Statut' ? 'Pendant les heures de bureau, les appelants peuvent naviguer dans le menu ; en dehors des heures de bureau, ils suivront la règle hors heures.' : 'During office hours, callers can navigate the menu; outside office hours they will follow the after-hours rule.'}
            </p>
            <form onSubmit={handleSavePBX} className="space-y-6">
              <section>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{t?.phoneNumbers?.businessHours || 'Business Hours'}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                  {t.common.status === 'Statut' ? 'Sélectionnez le fuseau horaire, les heures d\'ouverture et les jours où les appelants doivent entendre le menu IVR.' : 'Select the timezone, opening hours, and days when callers should hear the IVR menu.'}
                </p>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">{t?.phoneNumbers?.timezone || 'Timezone'}</label>
                    <select
                      value={pbxForm.business_hours.timezone}
                      onChange={(e) => updateBusinessHours('timezone', e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    >
                      {timezoneOptions.map((tz) => (
                        <option key={tz} value={tz}>
                          {tz}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium mb-1">{t?.phoneNumbers?.openTime || 'Open Time'}</label>
                      <input
                        type="time"
                        value={pbxForm.business_hours.open_time}
                        onChange={(e) => updateBusinessHours('open_time', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">{t?.phoneNumbers?.closeTime || 'Close Time'}</label>
                      <input
                        type="time"
                        value={pbxForm.business_hours.close_time}
                        onChange={(e) => updateBusinessHours('close_time', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                        required
                      />
                    </div>
                  </div>
                </div>
                <div className="mt-4">
                  <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.activeDays || 'Active Days'}</label>
                  <div className="flex flex-wrap gap-2">
                    {dayOptions.map((day) => {
                      const isActive = pbxForm.business_hours.days.includes(day.value);
                      return (
                        <button
                          type="button"
                          key={day.value}
                          onClick={() => toggleBusinessDay(day.value)}
                          className={`px-3 py-1.5 rounded-full text-sm border transition ${
                            isActive
                              ? 'bg-indigo-600 text-white border-indigo-600'
                              : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-indigo-400'
                          }`}
                        >
                          {day.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </section>

              <section>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{t?.phoneNumbers?.menuOptions || 'Menu Options'}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                  {t.common.status === 'Statut' ? 'Définissez les options du clavier que les appelants peuvent appuyer pendant les heures de bureau.' : 'Define the keypad options callers can press during business hours.'}
                </p>
                <div className="space-y-4">
                  {pbxForm.menu_options.map((option, index) => (
                    <div
                      key={`menu-option-${index}`}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-800/40 space-y-3"
                    >
                      <div className="flex justify-between items-center">
                        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                          {t?.phoneNumbers?.option || 'Option'} #{index + 1}
                        </h4>
                        {pbxForm.menu_options.length > 1 && (
                          <button
                            type="button"
                            onClick={() => removeMenuOption(index)}
                            className="text-red-600 hover:text-red-700 flex items-center gap-1 text-sm"
                          >
                            <TrashIcon className="h-4 w-4" />
                            {t?.common?.delete || 'Delete'}
                          </button>
                        )}
                      </div>
                      <div className="grid md:grid-cols-6 gap-3">
                        <div className="md:col-span-1">
                          <label className="block text-sm font-medium mb-1">{t?.phoneNumbers?.key || 'Key'}</label>
                          <input
                            type="text"
                            maxLength={1}
                            value={option.key}
                            onChange={(e) => updateMenuOption(index, 'key', e.target.value.replace(/\D/g, ''))}
                            className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                            placeholder="1"
                            required
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-sm font-medium mb-1">{t?.phoneNumbers?.label || 'Label'}</label>
                          <input
                            type="text"
                            value={option.label || ''}
                            onChange={(e) => updateMenuOption(index, 'label', e.target.value)}
                            className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                            placeholder={t?.phoneNumbers?.speakToSales || 'Speak to sales'}
                          />
                        </div>
                        <div className="md:col-span-3">
                          <label className="block text-sm font-medium mb-1">{t?.phoneNumbers?.destination || 'Destination'}</label>
                          <div className="grid grid-cols-2 gap-2">
                            <select
                              value={option.destination_type}
                              onChange={(e) =>
                                updateMenuOption(
                                  index,
                                  'destination_type',
                                  e.target.value as PBXMenuOption['destination_type']
                                )
                              }
                              className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                            >
                              <option value="agent">{t.common.status === 'Statut' ? 'Agent IA (extension)' : 'AI Agent (extension)'}</option>
                              <option value="forward">{t.common.status === 'Statut' ? 'Transférer vers téléphone' : 'Forward to phone'}</option>
                              <option value="voicemail">{t.common.status === 'Statut' ? 'Messagerie vocale' : 'Voicemail'}</option>
                              <option value="external">{t.common.status === 'Statut' ? 'Action externe' : 'External action'}</option>
                            </select>
                            {option.destination_type !== 'agent' && (
                              <input
                                type="text"
                                value={option.destination_value || ''}
                                onChange={(e) => updateMenuOption(index, 'destination_value', e.target.value)}
                                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                                placeholder={
                                  option.destination_type === 'voicemail'
                                    ? (t.common.status === 'Statut' ? 'ID de boîte vocale' : 'Mailbox ID')
                                    : (t.common.status === 'Statut' ? 'Destination (ex: +33123456789)' : 'Destination (e.g., +33123456789)')
                                }
                                required
                              />
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="pt-2">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={addMenuOption}
                    className="text-indigo-600 hover:text-indigo-700"
                  >
                    <PlusCircleIcon className="h-5 w-5" />
                    {t?.phoneNumbers?.addMenuOption || 'Add Menu Option'}
                  </Button>
                </div>
              </section>

              <section>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{t?.phoneNumbers?.afterHoursRouting || 'After Hours Routing'}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                  {t.common.status === 'Statut' ? 'Choisissez ce qui se passe lorsque les clients appellent en dehors des heures de bureau.' : 'Choose what happens when customers call outside of business hours.'}
                </p>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">{t.common.status === 'Statut' ? 'Destination' : 'Destination'}</label>
                    <select
                      value={pbxForm.after_hours_routing.destination_type}
                      onChange={(e) =>
                        updateAfterHours(
                          'destination_type',
                          e.target.value as AfterHoursRouting['destination_type']
                        )
                      }
                      className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    >
                      <option value="agent">{t?.phoneNumbers?.connectToAIAgent || 'Connect to AI Agent'}</option>
                      <option value="forward">{t?.common?.status === 'Statut' ? 'Transférer vers téléphone humain' : 'Forward to human phone'}</option>
                      <option value="voicemail">{t?.phoneNumbers?.sendToVoicemail || 'Send to Voicemail'}</option>
                      <option value="external">{(t?.phoneNumbers?.externalDestination || 'External Destination').replace(':', '')}</option>
                    </select>
                  </div>
                  {pbxForm.after_hours_routing.destination_type !== 'agent' && (
                    <div>
                      <label className="block text-sm font-medium mb-1">
                        {t?.phoneNumbers?.destinationValue || 'Destination Value'}
                      </label>
                      <input
                        type="text"
                        value={pbxForm.after_hours_routing.destination_value || ''}
                        onChange={(e) => updateAfterHours('destination_value', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                        placeholder={t.common.status === 'Statut' ? 'ex: +33123456789 ou ID de boîte vocale' : 'e.g., +33123456789 or mailbox id'}
                        required
                      />
                    </div>
                  )}
                </div>
                <div className="mt-3">
                  <label className="block text-sm font-medium mb-1">{t?.phoneNumbers?.message || 'Message'} ({t?.phoneNumbers?.optional || 'Optional'})</label>
                  <textarea
                    value={pbxForm.after_hours_routing.message || ''}
                    onChange={(e) => updateAfterHours('message', e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    rows={3}
                    placeholder={t.common.status === 'Statut' ? 'Nos bureaux sont actuellement fermés...' : 'Our offices are currently closed...'}
                  />
                </div>
              </section>

              <div className="flex flex-col md:flex-row md:justify-end gap-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={closePBXModal}
                  className="md:w-auto w-full"
                  disabled={pbxSaving}
                >
                  {t?.common?.cancel || 'Cancel'}
                </Button>
                <Button type="submit" className="md:w-auto w-full" loading={pbxSaving}>
                  {pbxSaving ? (t?.phoneNumbers?.saving || 'Saving...') : (t?.phoneNumbers?.savePBX || 'Save PBX')}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
      </div>
    </DashboardLayout>
  );
};

