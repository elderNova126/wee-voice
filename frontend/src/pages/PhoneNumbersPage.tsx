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
  TrashIcon,
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
  // SIP Configuration
  sip_websocket_url?: string | null;
  sip_transport?: string | null;
  sip_username?: string | null;
  sip_domain?: string | null;
  has_sip_config?: boolean;
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
    business_name: '',
    sip_config: {
      websocket_url: 'wss://weevoice.weedoo.com:8089/ws',
      transport: 'WSS',
      username: '',
      password: '',
      domain: 'weevoice.weedoo.com'
    }
  });
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [phoneNumberToDelete, setPhoneNumberToDelete] = useState<PhoneNumber | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [uploadData, setUploadData] = useState({
    document_type: 'company_registration',
    file: null as File | null
  });

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
      // Prepare request data with SIP config
      const requestData = {
        phone_number: existingNumberData.phone_number,
        country_code: existingNumberData.country_code,
        business_name: existingNumberData.business_name,
        sip_config: {
          websocket_url: existingNumberData.sip_config.websocket_url,
          transport: existingNumberData.sip_config.transport,
          username: existingNumberData.sip_config.username,
          password: existingNumberData.sip_config.password,
          domain: existingNumberData.sip_config.domain
        }
      };
      
      await api.post('/phone-numbers/add-existing', requestData);
      await loadPhoneNumbers();
      setShowAddExistingModal(false);
      setExistingNumberData({
        phone_number: '',
        country_code: 'BE',
        business_name: '',
        sip_config: {
          websocket_url: 'wss://weevoice.weedoo.com:8089/ws',
          transport: 'WSS',
          username: '',
          password: '',
          domain: 'weevoice.weedoo.com'
        }
      });
      toast.success(t.phoneNumbers.phoneNumberAddedSuccess);
    } catch (error: any) {
      toast.error(t.phoneNumbers.createError + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setRequestLoading(false);
    }
  };

  const handleDeletePhoneNumber = async () => {
    if (!phoneNumberToDelete) return;
    
    setDeleteLoading(true);
    try {
      await api.delete(`/phone-numbers/${phoneNumberToDelete.id}`);
      await loadPhoneNumbers();
      setShowDeleteModal(false);
      setPhoneNumberToDelete(null);
      toast.success(t?.phoneNumbers?.phoneNumberDeletedSuccess || 'Phone number deleted successfully');
    } catch (error: any) {
      toast.error((t?.phoneNumbers?.deleteError || 'Failed to delete phone number') + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setDeleteLoading(false);
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
                        {t?.phoneNumbers?.sipConfiguration || 'SIP Configuration'}
                      </div>
                      {number.has_sip_config ? (
                        <div className="space-y-1 text-gray-700 dark:text-gray-300 bg-green-50 dark:bg-green-900/20 p-2 rounded-lg">
                          <div className="flex items-center gap-1 text-green-700 dark:text-green-400 font-medium">
                            <CheckCircleIcon className="h-4 w-4" />
                            {t?.phoneNumbers?.sipConfigured || 'SIP Configured'}
                          </div>
                          <div className="text-xs text-gray-600 dark:text-gray-400">
                            <span className="font-medium">{t?.phoneNumbers?.websocketUrl || 'WebSocket URL'}:</span>{' '}
                            <span className="font-mono">{number.sip_websocket_url}</span>
                          </div>
                          <div className="text-xs text-gray-600 dark:text-gray-400">
                            <span className="font-medium">{t?.phoneNumbers?.sipUsername || 'SIP Username'}:</span>{' '}
                            <span className="font-mono">{number.sip_username}@{number.sip_domain}</span>
                          </div>
                        </div>
                      ) : (
                        <p className="text-amber-600 dark:text-amber-400">
                          {t?.phoneNumbers?.sipConfigDesc || 'SIP not configured - add SIP settings to handle incoming calls'}
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
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 border-red-300 dark:border-red-700"
                      onClick={() => {
                        setPhoneNumberToDelete(number);
                        setShowDeleteModal(true);
                      }}
                    >
                      <TrashIcon className="mr-2 h-3.5 w-3.5" />
                      {t?.common?.delete || 'Delete'}
                    </Button>
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
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 px-4">
          <Card className="max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-4">{t?.phoneNumbers?.addExistingPhoneNumber || 'Add Existing Phone Number'}</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              {t?.phoneNumbers?.addExistingDesc || 'Add your phone number with SIP configuration for incoming calls'}
            </p>
            <form onSubmit={handleAddExistingNumber} className="space-y-6">
              {/* Phone Number Section */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white border-b border-gray-200 dark:border-gray-700 pb-2">
                  {t?.phoneNumbers?.phoneNumberDetails || 'Phone Number Details'}
                </h3>
                
                <div>
                  <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.phoneNumberLabel || 'Phone Number'}</label>
                  <input
                    type="text"
                    required
                    value={existingNumberData.phone_number}
                    onChange={(e) => setExistingNumberData({ ...existingNumberData, phone_number: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    placeholder={t?.phoneNumbers?.phoneNumberPlaceholder || '+32 2 833 2888'}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
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
                </div>
              </div>

              {/* SIP Configuration Section */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white border-b border-gray-200 dark:border-gray-700 pb-2">
                  {t?.phoneNumbers?.sipConfiguration || 'SIP Configuration'}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {t?.phoneNumbers?.sipConfigDesc || 'Configure SIP settings for handling incoming calls with the AI agent'}
                </p>
                
                <div>
                  <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.websocketUrl || 'WebSocket (WSS) URL'}</label>
                  <input
                    type="text"
                    required
                    value={existingNumberData.sip_config.websocket_url}
                    onChange={(e) => setExistingNumberData({ 
                      ...existingNumberData, 
                      sip_config: { ...existingNumberData.sip_config, websocket_url: e.target.value }
                    })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700 font-mono text-sm"
                    placeholder="wss://weevoice.weedoo.com:8089/ws"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.transport || 'Transport'}</label>
                    <select
                      value={existingNumberData.sip_config.transport}
                      onChange={(e) => setExistingNumberData({ 
                        ...existingNumberData, 
                        sip_config: { ...existingNumberData.sip_config, transport: e.target.value }
                      })}
                      className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                    >
                      <option value="WSS">WSS (WebSocket Secure)</option>
                      <option value="WS">WS (WebSocket)</option>
                      <option value="UDP">UDP</option>
                      <option value="TCP">TCP</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.sipUsername || 'SIP Username'}</label>
                    <input
                      type="text"
                      required
                      value={existingNumberData.sip_config.username}
                      onChange={(e) => setExistingNumberData({ 
                        ...existingNumberData, 
                        sip_config: { ...existingNumberData.sip_config, username: e.target.value }
                      })}
                      className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700 font-mono"
                      placeholder="55555"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.sipPassword || 'Password'}</label>
                  <input
                    type="password"
                    required
                    value={existingNumberData.sip_config.password}
                    onChange={(e) => setExistingNumberData({ 
                      ...existingNumberData, 
                      sip_config: { ...existingNumberData.sip_config, password: e.target.value }
                    })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700 font-mono"
                    placeholder="••••••••••••••••"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">{t?.phoneNumbers?.sipDomain || 'Domain/Realm'}</label>
                  <input
                    type="text"
                    required
                    value={existingNumberData.sip_config.domain}
                    onChange={(e) => setExistingNumberData({ 
                      ...existingNumberData, 
                      sip_config: { ...existingNumberData.sip_config, domain: e.target.value }
                    })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700 font-mono"
                    placeholder="weevoice.weedoo.com"
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
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

      {/* Delete Confirmation Modal */}
      {showDeleteModal && phoneNumberToDelete && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-md w-full">
            <div className="text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/30 mb-4">
                <TrashIcon className="h-6 w-6 text-red-600 dark:text-red-400" />
              </div>
              <h2 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">
                {t?.phoneNumbers?.deletePhoneNumber || 'Delete Phone Number'}
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                {t?.phoneNumbers?.deleteConfirmation || 'Are you sure you want to delete this phone number?'}
              </p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
                {phoneNumberToDelete.phone_number}
              </p>
              {phoneNumberToDelete.agent_id && (
                <p className="text-sm text-amber-600 dark:text-amber-400 mb-4">
                  {t?.phoneNumbers?.deleteWarningAgent || 'This phone number is currently assigned to an agent.'}
                </p>
              )}
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => {
                    setShowDeleteModal(false);
                    setPhoneNumberToDelete(null);
                  }}
                  disabled={deleteLoading}
                >
                  {t?.common?.cancel || 'Cancel'}
                </Button>
                <Button
                  className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                  onClick={handleDeletePhoneNumber}
                  disabled={deleteLoading}
                >
                  {deleteLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      {t?.phoneNumbers?.deleting || 'Deleting...'}
                    </>
                  ) : (
                    t?.common?.delete || 'Delete'
                  )}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      </div>
    </DashboardLayout>
  );
};

