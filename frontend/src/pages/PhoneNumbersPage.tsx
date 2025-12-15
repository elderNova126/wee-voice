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
  UserGroupIcon,
  Cog6ToothIcon,
  EnvelopeIcon,
  GlobeAltIcon,
  SignalIcon,
  BellAlertIcon,
} from '@heroicons/react/24/outline'

interface Collaborator {
  id: number;
  user_id: number;
  user_email: string;
  user_name: string | null;
  permissions: string;
  is_active: boolean;
  status?: string;
}

interface PendingInvite {
  id: number;
  user_id: number;
  user_email: string;
  user_name: string | null;
  permissions: string;
  status: string;
  phone_number_id: number;
  phone_number_display: string;
  business_name?: string;
  invited_by_email?: string;
}

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
  sip_password?: string | null;
  sip_domain?: string | null;
  has_sip_config?: boolean;
  // Busy line behavior
  busy_action?: 'busy_tone' | 'voicemail' | string;
  busy_audio_file_url?: string | null;
  // Call restrictions
  restriction_mode?: 'none' | 'blacklist' | 'whitelist' | string;
  blocked_countries?: string[];
  blocked_numbers?: string[];
  allowed_countries?: string[];
  // Collaborators
  collaborators?: Collaborator[];
  // Ownership info
  is_owner?: boolean;
  role?: 'owner' | 'collaborator';
  permissions?: string[];
  owner_email?: string | null;
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

interface EditDataType {
  business_name: string;
  sip_websocket_url: string;
  sip_transport: string;
  sip_username: string;
  sip_password: string;
  sip_domain: string;
  busy_action: 'busy_tone' | 'voicemail';
  busy_audio_file_url: string;
  restriction_mode: 'none' | 'blacklist' | 'whitelist';
  blocked_countries: string[];
  blocked_numbers: string[];
  allowed_countries: string[];
  newBlockedNumber: string;
  newBlockedCountry: string;
  newAllowedCountry: string;
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
  
  // Pending invites
  const [pendingInvites, setPendingInvites] = useState<PendingInvite[]>([]);
  const [inviteLoading, setInviteLoading] = useState(false);
  
  // Edit phone number modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editAudioUploading, setEditAudioUploading] = useState(false);
  
  // Collaborators modal
  const [showCollaboratorsModal, setShowCollaboratorsModal] = useState(false);
  const [collaboratorEmail, setCollaboratorEmail] = useState('');
  const [collaboratorPermissions, setCollaboratorPermissions] = useState('view,edit');
  const [collaboratorLoading, setCollaboratorLoading] = useState(false);
  
  const [editData, setEditData] = useState<EditDataType>({
    business_name: '',
    sip_websocket_url: '',
    sip_transport: 'WSS',
    sip_username: '',
    sip_password: '',
    sip_domain: '',
    busy_action: 'busy_tone',
    busy_audio_file_url: '',
    restriction_mode: 'none',
    blocked_countries: [],
    blocked_numbers: [],
    allowed_countries: [],
    newBlockedNumber: '',
    newBlockedCountry: '',
    newAllowedCountry: ''
  });

  const [uploadData, setUploadData] = useState({
    document_type: 'company_registration',
    file: null as File | null
  });

  useEffect(() => {
    loadPhoneNumbers();
    loadAgents();
    loadPendingInvites();
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

  const loadPendingInvites = async () => {
    try {
      const response = await api.get('/phone-numbers/invites/pending');
      setPendingInvites(response.data);
    } catch (error) {
      console.error('Error loading pending invites:', error);
    }
  };

  const handleRespondToInvite = async (phoneNumberId: number, action: 'accept' | 'reject') => {
    setInviteLoading(true);
    try {
      await api.post(`/phone-numbers/invites/${phoneNumberId}/respond`, { action });
      toast.success(action === 'accept' ? 
        (t?.phoneNumbers?.inviteAccepted || 'Invite accepted!') : 
        (t?.phoneNumbers?.inviteRejected || 'Invite rejected'));
      await loadPendingInvites();
      await loadPhoneNumbers();
    } catch (error: any) {
      toast.error((t?.phoneNumbers?.inviteError || 'Failed to respond to invite') + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setInviteLoading(false);
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

  const handleEditAudioUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedNumber || !e.target.files || e.target.files.length === 0) return;
    
    const file = e.target.files[0];
    const allowedTypes = ['audio/wav', 'audio/mpeg', 'audio/mp3', 'audio/ogg', 'audio/webm'];
    
    if (!allowedTypes.includes(file.type)) {
      toast.error('Please upload a valid audio file (WAV, MP3, OGG, or WebM)');
      return;
    }
    
    setEditAudioUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await api.post(`/phone-numbers/${selectedNumber.id}/busy-audio`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setEditData((prev: EditDataType) => ({
        ...prev,
        busy_audio_file_url: response.data.file_url
      }));
      
      toast.success('Audio file uploaded successfully');
    } catch (error: any) {
      toast.error('Failed to upload audio: ' + (error.response?.data?.detail || error.message));
    } finally {
      setEditAudioUploading(false);
    }
  };

  const handleSavePhoneNumber = async () => {
    if (!selectedNumber) return;
    
    setEditLoading(true);
    try {
      await api.put(`/phone-numbers/${selectedNumber.id}`, {
        business_name: editData.business_name,
        sip_websocket_url: editData.sip_websocket_url,
        sip_transport: editData.sip_transport,
        sip_username: editData.sip_username,
        sip_password: editData.sip_password || undefined,
        sip_domain: editData.sip_domain,
        busy_action: editData.busy_action,
        busy_audio_file_url: editData.busy_audio_file_url || undefined,
        restriction_mode: editData.restriction_mode,
        blocked_countries: editData.blocked_countries,
        blocked_numbers: editData.blocked_numbers,
        allowed_countries: editData.allowed_countries
      });
      
      await loadPhoneNumbers();
      setShowEditModal(false);
      toast.success('Phone number settings updated successfully');
    } catch (error: any) {
      toast.error('Failed to update: ' + (error.response?.data?.detail || error.message));
    } finally {
      setEditLoading(false);
    }
  };

  const openEditModal = (number: PhoneNumber) => {
    setSelectedNumber(number);
    setEditData({
      business_name: number.business_name || '',
      sip_websocket_url: number.sip_websocket_url || '',
      sip_transport: number.sip_transport || 'WSS',
      sip_username: number.sip_username || '',
      sip_password: number.sip_password || '',
      sip_domain: number.sip_domain || '',
      busy_action: (number.busy_action || 'busy_tone') as 'busy_tone' | 'voicemail',
      busy_audio_file_url: number.busy_audio_file_url || '',
      restriction_mode: (number.restriction_mode || 'none') as 'none' | 'blacklist' | 'whitelist',
      blocked_countries: number.blocked_countries || [],
      blocked_numbers: number.blocked_numbers || [],
      allowed_countries: number.allowed_countries || [],
      newBlockedNumber: '',
      newBlockedCountry: '',
      newAllowedCountry: ''
    });
    setShowEditModal(true);
  };

  const openCollaboratorsModal = (number: PhoneNumber) => {
    setSelectedNumber(number);
    setCollaboratorEmail('');
    setCollaboratorPermissions('view,edit');
    setShowCollaboratorsModal(true);
  };

  const handleAddCollaborator = async () => {
    if (!selectedNumber || !collaboratorEmail) return;
    
    setCollaboratorLoading(true);
    try {
      await api.post(`/phone-numbers/${selectedNumber.id}/collaborators`, {
        email: collaboratorEmail,
        permissions: collaboratorPermissions
      });
      toast.success(t?.phoneNumbers?.collaboratorAdded || 'Collaborator added successfully');
      setCollaboratorEmail('');
      // Reload phone numbers and update selectedNumber
      const response = await api.get('/phone-numbers/');
      setPhoneNumbers(response.data);
      const updated = response.data.find((p: PhoneNumber) => p.id === selectedNumber.id);
      if (updated) setSelectedNumber(updated);
    } catch (error: any) {
      toast.error((t?.phoneNumbers?.collaboratorError || 'Failed to add collaborator') + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setCollaboratorLoading(false);
    }
  };

  const handleRemoveCollaborator = async (collaboratorId: number) => {
    if (!selectedNumber) return;
    
    if (!confirm(t?.phoneNumbers?.confirmRemoveCollaborator || 'Remove this collaborator?')) return;
    
    try {
      await api.delete(`/phone-numbers/${selectedNumber.id}/collaborators/${collaboratorId}`);
      toast.success(t?.phoneNumbers?.collaboratorRemoved || 'Collaborator removed');
      // Reload phone numbers and update selectedNumber
      const response = await api.get('/phone-numbers/');
      setPhoneNumbers(response.data);
      const updated = response.data.find((p: PhoneNumber) => p.id === selectedNumber.id);
      if (updated) setSelectedNumber(updated);
    } catch (error: any) {
      toast.error((t?.phoneNumbers?.collaboratorError || 'Failed to remove collaborator') + ': ' + (error.response?.data?.detail || error.message));
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

  const getAgentName = (agentId: number | null): string => {
    if (!agentId) return t.common.status === 'Statut' ? 'Non assigné' : 'Not assigned';
    const agent = agents.find((a: Agent) => a.id === agentId);
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
      <div className="space-y-8">
      {/* Modern Header with gradient accent */}
      <div className="relative">
        <div className="absolute inset-0 bg-gradient-to-r from-indigo-600/10 via-purple-600/10 to-pink-600/10 dark:from-indigo-600/5 dark:via-purple-600/5 dark:to-pink-600/5 rounded-2xl blur-xl"></div>
        <div className="relative bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-2xl p-6 border border-gray-200/50 dark:border-gray-700/50">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl shadow-lg shadow-indigo-500/25">
                  <PhoneIcon className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300 bg-clip-text text-transparent">
                    {t?.phoneNumbers?.title || 'Phone Numbers'}
                  </h1>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t?.phoneNumbers?.subtitle || 'Manage phone numbers for your voice agents'}
                  </p>
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <Button 
                onClick={() => setShowAddExistingModal(true)}
                className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-lg shadow-indigo-500/25 border-0"
              >
                <PhoneIcon className="h-4 w-4 mr-2" />
                {t?.phoneNumbers?.addExistingNumber || 'Add Number'}
              </Button>
              <Button onClick={() => setShowRequestModal(true)} variant="outline" className="border-gray-300 dark:border-gray-600">
                {t?.phoneNumbers?.requestNewNumber || 'Request New'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Pending Invites Section */}
      {pendingInvites.length > 0 && (
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-r from-amber-500/10 to-orange-500/10 rounded-2xl blur-xl"></div>
          <div className="relative bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm rounded-2xl border border-amber-200/50 dark:border-amber-700/30 overflow-hidden">
            <div className="px-6 py-4 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border-b border-amber-200/50 dark:border-amber-700/30">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-100 dark:bg-amber-800/30 rounded-lg">
                  <BellAlertIcon className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <h2 className="font-semibold text-amber-900 dark:text-amber-100">
                    {t?.phoneNumbers?.pendingInvites || 'Pending Invites'}
                  </h2>
                  <p className="text-sm text-amber-700 dark:text-amber-300">
                    {t?.phoneNumbers?.pendingInvitesDesc || 'You have collaboration invites waiting for your response'}
                  </p>
                </div>
              </div>
            </div>
            <div className="p-4 space-y-3">
              {pendingInvites.map((invite) => (
                <div 
                  key={`${invite.phone_number_id}-${invite.user_id}`}
                  className="flex items-center justify-between p-4 bg-white dark:bg-gray-700/50 rounded-xl border border-gray-200 dark:border-gray-600/50 hover:shadow-md transition-all"
                >
                  <div className="flex items-center gap-4">
                    <div className="p-2.5 bg-gradient-to-br from-amber-400 to-orange-500 rounded-xl">
                      <PhoneIcon className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900 dark:text-white">
                        {invite.phone_number_display}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {invite.business_name && <span>{invite.business_name} • </span>}
                        {t?.phoneNumbers?.invitedBy || 'Invited by'}: <span className="font-medium">{invite.invited_by_email}</span>
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-600 rounded-full text-gray-600 dark:text-gray-300">
                          {invite.permissions}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => handleRespondToInvite(invite.phone_number_id, 'accept')}
                      disabled={inviteLoading}
                      className="bg-emerald-500 hover:bg-emerald-600 text-white border-0"
                    >
                      <CheckCircleIcon className="h-4 w-4 mr-1" />
                      {t?.phoneNumbers?.accept || 'Accept'}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRespondToInvite(invite.phone_number_id, 'reject')}
                      disabled={inviteLoading}
                      className="border-red-300 text-red-600 hover:bg-red-50 dark:border-red-700 dark:hover:bg-red-900/20"
                    >
                      <XCircleIcon className="h-4 w-4 mr-1" />
                      {t?.phoneNumbers?.reject || 'Reject'}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Phone Numbers Grid */}
      {phoneNumbers.length === 0 ? (
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-br from-gray-100 to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-2xl"></div>
          <div className="relative text-center py-16 px-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-indigo-100 to-purple-100 dark:from-indigo-900/50 dark:to-purple-900/50 rounded-2xl mb-6">
              <PhoneIcon className="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              {t?.phoneNumbers?.noPhoneNumbers || 'No Phone Numbers'}
            </h3>
            <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto mb-6">
              {t?.phoneNumbers?.noPhoneNumbersDesc || 'Add your existing phone number or request a new one to start receiving AI-powered calls'}
            </p>
            <div className="flex gap-3 justify-center">
              <Button 
                onClick={() => setShowAddExistingModal(true)}
                className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-lg border-0"
              >
                {t?.phoneNumbers?.addExistingNumber || 'Add Existing Number'}
              </Button>
              <Button onClick={() => setShowRequestModal(true)} variant="outline">
                {t?.phoneNumbers?.requestNewNumber || 'Request New Number'}
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid gap-5">
          {phoneNumbers.map((number: PhoneNumber) => (
            <div 
              key={number.id} 
              className={`group relative bg-white dark:bg-gray-800 rounded-2xl border transition-all duration-300 hover:shadow-xl ${
                number.role === 'collaborator' 
                  ? 'border-purple-200 dark:border-purple-700/50 hover:border-purple-300 dark:hover:border-purple-600' 
                  : 'border-gray-200 dark:border-gray-700 hover:border-indigo-300 dark:hover:border-indigo-600'
              }`}
            >
              {/* Subtle gradient overlay on hover */}
              <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl ${
                number.role === 'collaborator'
                  ? 'bg-gradient-to-br from-purple-50/50 to-pink-50/50 dark:from-purple-900/10 dark:to-pink-900/10'
                  : 'bg-gradient-to-br from-indigo-50/50 to-purple-50/50 dark:from-indigo-900/10 dark:to-purple-900/10'
              }`}></div>
              
              <div className="relative p-6">
                {/* Top row: Main info and status */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-start gap-4">
                    <div className={`p-3 rounded-xl shadow-sm ${
                      number.role === 'collaborator'
                        ? 'bg-gradient-to-br from-purple-500 to-pink-500'
                        : 'bg-gradient-to-br from-indigo-500 to-purple-500'
                    }`}>
                      <PhoneIcon className="h-6 w-6 text-white" />
                    </div>
                    <div>
                      <div className="flex items-center gap-3">
                        <h3 className="text-xl font-bold text-gray-900 dark:text-white tracking-tight">
                          {number.phone_number}
                        </h3>
                        {getStatusBadge(number.status)}
                        {number.role === 'collaborator' && (
                          <span className="px-2.5 py-1 bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 text-xs font-medium rounded-full">
                            {t?.phoneNumbers?.shared || 'Shared'}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-sm text-gray-500 dark:text-gray-400">
                        {number.business_name && <span className="font-medium text-gray-700 dark:text-gray-300">{number.business_name}</span>}
                        <span className="flex items-center gap-1">
                          <GlobeAltIcon className="h-3.5 w-3.5" />
                          {number.country_code}
                        </span>
                        {number.role === 'collaborator' && number.owner_email && (
                          <span className="text-purple-600 dark:text-purple-400">
                            {t?.phoneNumbers?.sharedBy || 'Shared by'}: {number.owner_email}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {/* Action buttons */}
                  <div className="flex items-center gap-2">
                    {(number.status === 'active' || number.status === 'approved') && (number.is_owner || number.permissions?.includes('edit')) && (
                      <>
                        <button
                          onClick={() => {
                            setSelectedNumber(number);
                            setSelectedAgentId(number.agent_id);
                            setShowAssignAgentModal(true);
                          }}
                          className="p-2 text-gray-500 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 rounded-lg transition-colors"
                          title={number.agent_id ? (t?.phoneNumbers?.changeAgent || 'Change Agent') : (t?.phoneNumbers?.assignAgent || 'Assign Agent')}
                        >
                          <UserGroupIcon className="h-5 w-5" />
                        </button>
                        <button
                          onClick={() => openEditModal(number)}
                          className="p-2 text-gray-500 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 rounded-lg transition-colors"
                          title={t?.phoneNumbers?.settings || 'Settings'}
                        >
                          <Cog6ToothIcon className="h-5 w-5" />
                        </button>
                      </>
                    )}
                    {(number.is_owner || number.permissions?.includes('delete')) && (
                      <button
                        onClick={() => {
                          setPhoneNumberToDelete(number);
                          setShowDeleteModal(true);
                        }}
                        className="p-2 text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                        title={t?.common?.delete || 'Delete'}
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Info Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                  {/* Agent Info */}
                  <div className="p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl">
                    <div className="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                      <UserGroupIcon className="h-3.5 w-3.5" />
                      {t?.phoneNumbers?.agent || 'Agent'}
                    </div>
                    <p className={`font-semibold ${number.agent_id ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                      {getAgentName(number.agent_id)}
                    </p>
                  </div>

                  {/* SIP Status */}
                  <div className="p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl">
                    <div className="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                      <SignalIcon className="h-3.5 w-3.5" />
                      {t?.phoneNumbers?.sipStatus || 'SIP Status'}
                    </div>
                    {number.has_sip_config ? (
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
                        <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                          {t?.phoneNumbers?.configured || 'Configured'}
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
                        <span className="font-semibold text-amber-600 dark:text-amber-400">
                          {t?.phoneNumbers?.notConfigured || 'Not Configured'}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Collaborators - Only for owners */}
                  {number.is_owner !== false && (
                    <div className="p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                          <EnvelopeIcon className="h-3.5 w-3.5" />
                          {t?.phoneNumbers?.collaborators || 'Collaborators'}
                        </div>
                        <button
                          onClick={() => openCollaboratorsModal(number)}
                          className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                        >
                          {t?.phoneNumbers?.manage || 'Manage'}
                        </button>
                      </div>
                      <div className="flex items-center gap-2">
                        {number.collaborators && number.collaborators.length > 0 ? (
                          <>
                            <div className="flex -space-x-2">
                              {number.collaborators.slice(0, 3).map((collab, idx) => (
                                <div 
                                  key={collab.id}
                                  className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-400 to-pink-500 flex items-center justify-center text-white text-xs font-medium border-2 border-white dark:border-gray-800"
                                  title={collab.user_name || collab.user_email}
                                >
                                  {(collab.user_name || collab.user_email).charAt(0).toUpperCase()}
                                </div>
                              ))}
                              {number.collaborators.length > 3 && (
                                <div className="w-7 h-7 rounded-full bg-gray-300 dark:bg-gray-600 flex items-center justify-center text-xs font-medium border-2 border-white dark:border-gray-800">
                                  +{number.collaborators.length - 3}
                                </div>
                              )}
                            </div>
                            <span className="text-sm text-gray-600 dark:text-gray-300">
                              {number.collaborators.length} {number.collaborators.length === 1 ? 'person' : 'people'}
                            </span>
                          </>
                        ) : (
                          <span className="text-sm text-gray-400">
                            {t?.phoneNumbers?.noCollaborators || 'None'}
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Permissions for collaborators */}
                  {number.role === 'collaborator' && number.permissions && (
                    <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-xl">
                      <div className="flex items-center gap-2 text-xs font-medium text-purple-600 dark:text-purple-400 uppercase tracking-wider mb-2">
                        <CheckCircleIcon className="h-3.5 w-3.5" />
                        {t?.phoneNumbers?.yourPermissions || 'Your Permissions'}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {number.permissions.map((perm) => (
                          <span key={perm} className="px-2 py-0.5 bg-purple-100 dark:bg-purple-800/50 text-purple-700 dark:text-purple-300 rounded-full text-xs font-medium">
                            {perm}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Upload documents button for pending status */}
                {(number.status === 'pending' || number.status === 'documents_submitted') && (
                  <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedNumber(number);
                        loadDocuments(number.id);
                        setShowUploadModal(true);
                      }}
                      className="w-full border-dashed"
                    >
                      <CloudArrowUpIcon className="mr-2 h-4 w-4" />
                      {t?.phoneNumbers?.uploadDocuments || 'Upload Verification Documents'}
                    </Button>
                  </div>
                )}
              </div>
            </div>
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
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setExistingNumberData({ ...existingNumberData, phone_number: e.target.value })}
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

      {/* Phone Number Settings Modal */}
      {showEditModal && selectedNumber && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 px-4 py-6 overflow-y-auto">
          <Card className="max-w-3xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                {t?.phoneNumbers?.phoneNumberSettings || 'Phone Number Settings'}: {selectedNumber.phone_number}
              </h2>
              <button
                onClick={() => setShowEditModal(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="space-y-6">
              {/* Business Info */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white border-b pb-2 mb-4">
                  Business Information
                </h3>
                <div>
                  <label className="block text-sm font-medium mb-2">Business Name</label>
                  <input
                    type="text"
                    value={editData.business_name}
                    onChange={(e) => setEditData({...editData, business_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                    placeholder="Your Company Name"
                  />
                </div>
              </div>

              {/* SIP Configuration */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white border-b pb-2 mb-4">
                  SIP Configuration
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">WebSocket URL</label>
                    <input
                      type="text"
                      value={editData.sip_websocket_url}
                      onChange={(e) => setEditData({...editData, sip_websocket_url: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                      placeholder="wss://server:8089/ws"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Transport</label>
                    <select
                      value={editData.sip_transport}
                      onChange={(e) => setEditData({...editData, sip_transport: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                    >
                      <option value="WSS">WSS (Secure WebSocket)</option>
                      <option value="WS">WS (WebSocket)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">SIP Username</label>
                    <input
                      type="text"
                      value={editData.sip_username}
                      onChange={(e) => setEditData({...editData, sip_username: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                      placeholder="55555"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">SIP Password</label>
                    <input
                      type="password"
                      value={editData.sip_password}
                      onChange={(e) => setEditData({...editData, sip_password: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                      placeholder="Enter SIP password"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium mb-2">SIP Domain</label>
                    <input
                      type="text"
                      value={editData.sip_domain}
                      onChange={(e) => setEditData({...editData, sip_domain: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                      placeholder="weevoice.example.com"
                    />
                  </div>
                </div>
              </div>

              {/* Busy Settings */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white border-b pb-2 mb-4">
                  Busy Line Settings
                </h3>
                <div className="space-y-4">
                  <div className="flex gap-4">
                    <label className="flex items-center space-x-2 cursor-pointer">
                      <input
                        type="radio"
                        name="edit_busy_action"
                        value="busy_tone"
                        checked={editData.busy_action === 'busy_tone'}
                        onChange={(e) => setEditData({...editData, busy_action: 'busy_tone'})}
                        className="h-4 w-4 text-indigo-600"
                      />
                      <span>Busy Tone</span>
                    </label>
                    <label className="flex items-center space-x-2 cursor-pointer">
                      <input
                        type="radio"
                        name="edit_busy_action"
                        value="voicemail"
                        checked={editData.busy_action === 'voicemail'}
                        onChange={(e) => setEditData({...editData, busy_action: 'voicemail'})}
                        className="h-4 w-4 text-indigo-600"
                      />
                      <span>Custom Audio Message</span>
                    </label>
                  </div>
                  
                  {editData.busy_action === 'voicemail' && (
                    <div>
                      {editData.busy_audio_file_url ? (
                        <div className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm text-green-700 dark:text-green-300 font-medium">Audio uploaded</span>
                            <button
                              type="button"
                              onClick={() => setEditData({...editData, busy_audio_file_url: ''})}
                              className="text-red-600 hover:text-red-700 text-sm"
                            >
                              Remove
                            </button>
                          </div>
                          <audio controls className="w-full" src={editData.busy_audio_file_url} />
                        </div>
                      ) : (
                        <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-4 text-center">
                          <input
                            type="file"
                            accept="audio/*"
                            onChange={handleEditAudioUpload}
                            className="hidden"
                            id="edit-audio-upload"
                            disabled={editAudioUploading}
                          />
                          <label htmlFor="edit-audio-upload" className="cursor-pointer">
                            {editAudioUploading ? (
                              <span className="text-sm text-gray-600">Uploading...</span>
                            ) : (
                              <span className="text-sm text-indigo-600 font-medium">Click to upload audio</span>
                            )}
                          </label>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Call Restrictions */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white border-b pb-2 mb-4">
                  Call Restrictions
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Restriction Mode</label>
                    <select
                      value={editData.restriction_mode}
                      onChange={(e) => setEditData({...editData, restriction_mode: e.target.value as any})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                    >
                      <option value="none">No Restrictions - Accept all calls</option>
                      <option value="blacklist">Blacklist - Block specific countries/numbers</option>
                      <option value="whitelist">Whitelist - Only allow specific countries</option>
                    </select>
                  </div>
                  
                  {editData.restriction_mode === 'blacklist' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-2">Blocked Countries</label>
                        <div className="flex gap-2 mb-2">
                          <input
                            type="text"
                            value={editData.newBlockedCountry}
                            onChange={(e) => setEditData({...editData, newBlockedCountry: e.target.value.toUpperCase()})}
                            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                            placeholder="Country code (e.g., US, UK)"
                            maxLength={3}
                          />
                          <Button
                            size="sm"
                            onClick={() => {
                              if (editData.newBlockedCountry && !editData.blocked_countries.includes(editData.newBlockedCountry)) {
                                setEditData({
                                  ...editData,
                                  blocked_countries: [...editData.blocked_countries, editData.newBlockedCountry],
                                  newBlockedCountry: ''
                                });
                              }
                            }}
                          >
                            Add
                          </Button>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {editData.blocked_countries.map((country) => (
                            <span key={country} className="inline-flex items-center px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 rounded text-sm">
                              {country}
                              <button
                                onClick={() => setEditData({
                                  ...editData,
                                  blocked_countries: editData.blocked_countries.filter(c => c !== country)
                                })}
                                className="ml-1 text-red-600 hover:text-red-800"
                              >
                                ×
                              </button>
                            </span>
                          ))}
                        </div>
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-2">Blocked Phone Numbers</label>
                        <div className="flex gap-2 mb-2">
                          <input
                            type="text"
                            value={editData.newBlockedNumber}
                            onChange={(e) => setEditData({...editData, newBlockedNumber: e.target.value})}
                            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                            placeholder="+1234567890 or pattern like +1*"
                          />
                          <Button
                            size="sm"
                            onClick={() => {
                              if (editData.newBlockedNumber && !editData.blocked_numbers.includes(editData.newBlockedNumber)) {
                                setEditData({
                                  ...editData,
                                  blocked_numbers: [...editData.blocked_numbers, editData.newBlockedNumber],
                                  newBlockedNumber: ''
                                });
                              }
                            }}
                          >
                            Add
                          </Button>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {editData.blocked_numbers.map((num) => (
                            <span key={num} className="inline-flex items-center px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 rounded text-sm">
                              {num}
                              <button
                                onClick={() => setEditData({
                                  ...editData,
                                  blocked_numbers: editData.blocked_numbers.filter(n => n !== num)
                                })}
                                className="ml-1 text-red-600 hover:text-red-800"
                              >
                                ×
                              </button>
                            </span>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                  
                  {editData.restriction_mode === 'whitelist' && (
                    <div>
                      <label className="block text-sm font-medium mb-2">Allowed Countries (only these can call)</label>
                      <div className="flex gap-2 mb-2">
                        <input
                          type="text"
                          value={editData.newAllowedCountry}
                          onChange={(e) => setEditData({...editData, newAllowedCountry: e.target.value.toUpperCase()})}
                          className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                          placeholder="Country code (e.g., BE, FR)"
                          maxLength={3}
                        />
                        <Button
                          size="sm"
                          onClick={() => {
                            if (editData.newAllowedCountry && !editData.allowed_countries.includes(editData.newAllowedCountry)) {
                              setEditData({
                                ...editData,
                                allowed_countries: [...editData.allowed_countries, editData.newAllowedCountry],
                                newAllowedCountry: ''
                              });
                            }
                          }}
                        >
                          Add
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {editData.allowed_countries.map((country) => (
                          <span key={country} className="inline-flex items-center px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 rounded text-sm">
                            {country}
                            <button
                              onClick={() => setEditData({
                                ...editData,
                                allowed_countries: editData.allowed_countries.filter(c => c !== country)
                              })}
                              className="ml-1 text-green-600 hover:text-green-800"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                      {editData.allowed_countries.length === 0 && (
                        <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">
                          Warning: No countries added - all calls will be blocked!
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            <div className="flex gap-3 mt-6 pt-4 border-t">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowEditModal(false)}
                disabled={editLoading}
              >
                Cancel
              </Button>
              <Button
                className="flex-1"
                onClick={handleSavePhoneNumber}
                disabled={editLoading}
              >
                {editLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Saving...
                  </>
                ) : (
                  'Save Changes'
                )}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Collaborators Modal */}
      {showCollaboratorsModal && selectedNumber && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 px-4">
          <Card className="max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                {t?.phoneNumbers?.manageCollaborators || 'Manage Collaborators'}
              </h2>
              <button
                onClick={() => setShowCollaboratorsModal(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              {t?.phoneNumbers?.collaboratorsFor || 'Collaborators for'} <strong>{selectedNumber.phone_number}</strong>
            </p>
            
            {/* Add Collaborator Form */}
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium mb-2">
                  {t?.phoneNumbers?.collaboratorEmail || 'Collaborator Email'}
                </label>
                <input
                  type="email"
                  value={collaboratorEmail}
                  onChange={(e) => setCollaboratorEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                  placeholder="user@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">
                  {t?.phoneNumbers?.permissions || 'Permissions'}
                </label>
                <select
                  value={collaboratorPermissions}
                  onChange={(e) => setCollaboratorPermissions(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                >
                  <option value="view">{t?.phoneNumbers?.viewOnly || 'View Only'}</option>
                  <option value="view,edit">{t?.phoneNumbers?.viewEdit || 'View & Edit'}</option>
                  <option value="view,edit,delete">{t?.phoneNumbers?.fullAccess || 'Full Access'}</option>
                </select>
              </div>
              <Button
                onClick={handleAddCollaborator}
                disabled={!collaboratorEmail || collaboratorLoading}
                className="w-full"
              >
                {collaboratorLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    {t?.phoneNumbers?.adding || 'Adding...'}
                  </>
                ) : (
                  <>
                    <UserGroupIcon className="h-4 w-4 mr-2" />
                    {t?.phoneNumbers?.addCollaborator || 'Add Collaborator'}
                  </>
                )}
              </Button>
            </div>
            
            {/* Current Collaborators List */}
            <div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                {t?.phoneNumbers?.currentCollaborators || 'Current Collaborators'}
              </h3>
              {selectedNumber.collaborators && selectedNumber.collaborators.length > 0 ? (
                <div className="space-y-2">
                  {selectedNumber.collaborators.map((collab: Collaborator) => (
                    <div
                      key={collab.id}
                      className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
                    >
                      <div>
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          {collab.user_name || collab.user_email}
                        </p>
                        <p className="text-xs text-gray-500">
                          {collab.user_email}
                        </p>
                        <span className="inline-block mt-1 px-2 py-0.5 bg-purple-100 dark:bg-purple-800 text-purple-700 dark:text-purple-300 rounded text-xs">
                          {collab.permissions.split(',').map((p: string) => p.trim()).join(', ')}
                        </span>
                      </div>
                      <button
                        onClick={() => handleRemoveCollaborator(collab.id)}
                        className="text-red-600 hover:text-red-700 p-1"
                        title={t?.phoneNumbers?.removeCollaborator || 'Remove collaborator'}
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                  {t?.phoneNumbers?.noCollaboratorsYet || 'No collaborators added yet'}
                </p>
              )}
            </div>
            
            <div className="mt-6 pt-4 border-t">
              <Button
                variant="outline"
                className="w-full"
                onClick={() => setShowCollaboratorsModal(false)}
              >
                {t?.common?.close || 'Close'}
              </Button>
            </div>
          </Card>
        </div>
      )}

      </div>
    </DashboardLayout>
  );
};

