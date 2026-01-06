import React, { useState, useEffect } from 'react';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import api from '../lib/api';
import { useTranslation } from '../lib/translations';
import toast from 'react-hot-toast';
import {
  GlobeAltIcon,
  MapPinIcon,
  PhoneIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CloudArrowUpIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

interface Country {
  code: string;
  name: string;
  prefix: string;
}

interface Destination {
  id: string;
  name: string;
  type: string;
  monthly_fee: string;
  setup_fee: string;
  docs_required: boolean;
}

interface AvailableNumber {
  id: string;
  number: string;
  number_formatted: string;
  monthly_fee: string;
  setup_fee: string;
  per_minute_incoming: string;
}

interface RequestNumberModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

type Step = 'country' | 'destination' | 'number' | 'documents' | 'confirm';

const STEPS: { id: Step; label: string; icon: React.ReactNode }[] = [
  { id: 'country', label: 'Country', icon: <GlobeAltIcon className="h-5 w-5" /> },
  { id: 'destination', label: 'City', icon: <MapPinIcon className="h-5 w-5" /> },
  { id: 'number', label: 'Number', icon: <PhoneIcon className="h-5 w-5" /> },
  { id: 'documents', label: 'Documents', icon: <DocumentTextIcon className="h-5 w-5" /> },
  { id: 'confirm', label: 'Confirm', icon: <CheckCircleIcon className="h-5 w-5" /> },
];

export const RequestNumberModal: React.FC<RequestNumberModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const t = useTranslation();
  
  // Wizard state
  const [currentStep, setCurrentStep] = useState<Step>('country');
  const [loading, setLoading] = useState(false);
  
  // Data state
  const [countries, setCountries] = useState<Country[]>([]);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [availableNumbers, setAvailableNumbers] = useState<AvailableNumber[]>([]);
  
  // Selection state
  const [selectedCountry, setSelectedCountry] = useState<Country | null>(null);
  const [selectedDestination, setSelectedDestination] = useState<Destination | null>(null);
  const [selectedNumber, setSelectedNumber] = useState<AvailableNumber | null>(null);
  const [businessName, setBusinessName] = useState('');
  const [purpose, setPurpose] = useState('AI Voice Agent');
  
  // Document state
  const [documentsGroupId, setDocumentsGroupId] = useState<string | null>(null);
  const [uploadedDocuments, setUploadedDocuments] = useState<string[]>([]);
  const [uploadLoading, setUploadLoading] = useState(false);
  
  // Search filter
  const [searchQuery, setSearchQuery] = useState('');
  
  // Load countries on mount
  useEffect(() => {
    if (isOpen) {
      loadCountries();
    }
  }, [isOpen]);
  
  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setCurrentStep('country');
      setSelectedCountry(null);
      setSelectedDestination(null);
      setSelectedNumber(null);
      setBusinessName('');
      setPurpose('AI Voice Agent');
      setDocumentsGroupId(null);
      setUploadedDocuments([]);
      setSearchQuery('');
    }
  }, [isOpen]);
  
  const loadCountries = async () => {
    setLoading(true);
    try {
      const response = await api.get('/virtual-numbers/countries');
      setCountries(response.data.countries || []);
    } catch (error: any) {
      toast.error('Failed to load countries: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };
  
  const loadDestinations = async (countryCode: string) => {
    setLoading(true);
    try {
      const response = await api.get(`/virtual-numbers/destinations/${countryCode}`);
      setDestinations(response.data.destinations || []);
    } catch (error: any) {
      toast.error('Failed to load destinations: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };
  
  const loadAvailableNumbers = async (directionId: string) => {
    setLoading(true);
    try {
      const response = await api.get(`/virtual-numbers/available/${directionId}`);
      setAvailableNumbers(response.data.numbers || []);
    } catch (error: any) {
      toast.error('Failed to load available numbers: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };
  
  const handleCountrySelect = (country: Country) => {
    setSelectedCountry(country);
    setSelectedDestination(null);
    setSelectedNumber(null);
    loadDestinations(country.code);
    setCurrentStep('destination');
  };
  
  const handleDestinationSelect = (destination: Destination) => {
    setSelectedDestination(destination);
    setSelectedNumber(null);
    loadAvailableNumbers(destination.id);
    setCurrentStep('number');
  };
  
  const handleNumberSelect = (number: AvailableNumber) => {
    setSelectedNumber(number);
    // Skip documents step if not required
    if (selectedDestination && !selectedDestination.docs_required) {
      setCurrentStep('confirm');
    } else {
      setCurrentStep('documents');
    }
  };
  
  const handleDocumentUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    setUploadLoading(true);
    
    try {
      // Create document group if not exists
      if (!documentsGroupId) {
        const groupResponse = await api.post('/virtual-numbers/documents/group');
        setDocumentsGroupId(groupResponse.data.group_id);
      }
      
      const file = e.target.files[0];
      const formData = new FormData();
      formData.append('group_id', documentsGroupId || '');
      formData.append('document_type', 'company_registration');
      formData.append('file', file);
      
      await api.post('/virtual-numbers/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setUploadedDocuments([...uploadedDocuments, file.name]);
      toast.success('Document uploaded successfully');
    } catch (error: any) {
      toast.error('Failed to upload document: ' + (error.response?.data?.detail || error.message));
    } finally {
      setUploadLoading(false);
    }
  };
  
  const handleOrder = async () => {
    if (!selectedNumber || !selectedCountry || !selectedDestination || !businessName.trim()) {
      toast.error('Please fill in all required fields');
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await api.post('/virtual-numbers/order', {
        number_id: selectedNumber.id,
        direction_id: selectedDestination.id,
        number: selectedNumber.number,
        country_code: selectedCountry.code,
        city_name: selectedDestination.name,
        business_name: businessName,
        monthly_fee: selectedNumber.monthly_fee,
        documents_group_id: documentsGroupId,
        purpose: purpose,
      });
      
      if (response.data.success) {
        toast.success('Phone number ordered successfully!');
        onSuccess();
        onClose();
      }
    } catch (error: any) {
      toast.error('Failed to order number: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };
  
  const goBack = () => {
    switch (currentStep) {
      case 'destination':
        setCurrentStep('country');
        break;
      case 'number':
        setCurrentStep('destination');
        break;
      case 'documents':
        setCurrentStep('number');
        break;
      case 'confirm':
        if (selectedDestination?.docs_required) {
          setCurrentStep('documents');
        } else {
          setCurrentStep('number');
        }
        break;
    }
  };
  
  const getCurrentStepIndex = () => {
    return STEPS.findIndex(s => s.id === currentStep);
  };
  
  // Filter items based on search query
  const filteredCountries = countries.filter(c => 
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.code.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  const filteredDestinations = destinations.filter(d =>
    d.name.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  const filteredNumbers = availableNumbers.filter(n =>
    n.number.includes(searchQuery) || n.number_formatted.includes(searchQuery)
  );
  
  if (!isOpen) return null;
  
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 px-4">
      <Card className="max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              {t?.phoneNumbers?.requestNewPhoneNumber || 'Request Virtual Number'}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Order a new virtual phone number from Zadarma
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        
        {/* Progress Steps */}
        <div className="px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            {STEPS.map((step, index) => {
              const isActive = currentStep === step.id;
              const isCompleted = getCurrentStepIndex() > index;
              const isDisabled = 
                (step.id === 'documents' && selectedDestination && !selectedDestination.docs_required);
              
              if (isDisabled) return null;
              
              return (
                <React.Fragment key={step.id}>
                  <div className={`flex items-center gap-2 ${isActive ? 'text-indigo-600 dark:text-indigo-400' : isCompleted ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}`}>
                    <div className={`p-2 rounded-full ${isActive ? 'bg-indigo-100 dark:bg-indigo-900/50' : isCompleted ? 'bg-green-100 dark:bg-green-900/50' : 'bg-gray-100 dark:bg-gray-700'}`}>
                      {isCompleted ? <CheckCircleIcon className="h-5 w-5" /> : step.icon}
                    </div>
                    <span className="text-sm font-medium hidden sm:inline">{step.label}</span>
                  </div>
                  {index < STEPS.length - 1 && !(STEPS[index + 1].id === 'documents' && selectedDestination && !selectedDestination.docs_required) && (
                    <div className={`flex-1 h-0.5 mx-2 ${isCompleted ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-700'}`} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Search Input (for country, destination, number steps) */}
          {['country', 'destination', 'number'].includes(currentStep) && (
            <div className="mb-4">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={`Search ${currentStep === 'country' ? 'countries' : currentStep === 'destination' ? 'cities' : 'numbers'}...`}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
          )}
          
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          ) : (
            <>
              {/* Country Selection */}
              {currentStep === 'country' && (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {filteredCountries.map((country) => (
                    <button
                      key={country.code}
                      onClick={() => handleCountrySelect(country)}
                      className={`p-4 rounded-xl border-2 text-left transition-all hover:shadow-md ${
                        selectedCountry?.code === country.code
                          ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-900/20'
                          : 'border-gray-200 dark:border-gray-700 hover:border-indigo-400'
                      }`}
                    >
                      <div className="font-semibold text-gray-900 dark:text-white">{country.name}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">{country.prefix}</div>
                    </button>
                  ))}
                </div>
              )}
              
              {/* Destination Selection */}
              {currentStep === 'destination' && (
                <div className="space-y-3">
                  {filteredDestinations.map((dest) => (
                    <button
                      key={dest.id}
                      onClick={() => handleDestinationSelect(dest)}
                      className={`w-full p-4 rounded-xl border-2 text-left transition-all hover:shadow-md ${
                        selectedDestination?.id === dest.id
                          ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-900/20'
                          : 'border-gray-200 dark:border-gray-700 hover:border-indigo-400'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white">{dest.name}</div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs text-gray-600 dark:text-gray-300 capitalize">
                              {dest.type}
                            </span>
                            {dest.docs_required && (
                              <span className="px-2 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 rounded text-xs">
                                Documents Required
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold text-indigo-600 dark:text-indigo-400">€{dest.monthly_fee}/mo</div>
                          {dest.setup_fee !== '0.00' && (
                            <div className="text-xs text-gray-500">+ €{dest.setup_fee} setup</div>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              
              {/* Number Selection */}
              {currentStep === 'number' && (
                <div className="space-y-2">
                  {filteredNumbers.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                      No numbers available. Please try another destination.
                    </div>
                  ) : (
                    filteredNumbers.map((num) => (
                      <button
                        key={num.id}
                        onClick={() => handleNumberSelect(num)}
                        className={`w-full p-4 rounded-xl border-2 text-left transition-all hover:shadow-md ${
                          selectedNumber?.id === num.id
                            ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-900/20'
                            : 'border-gray-200 dark:border-gray-700 hover:border-indigo-400'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="font-mono text-lg font-bold text-gray-900 dark:text-white">
                            {num.number_formatted}
                          </div>
                          <div className="text-right">
                            <div className="font-bold text-indigo-600 dark:text-indigo-400">€{num.monthly_fee}/mo</div>
                          </div>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              )}
              
              {/* Documents Upload */}
              {currentStep === 'documents' && (
                <div className="space-y-6">
                  <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl p-4">
                    <h3 className="font-semibold text-amber-800 dark:text-amber-300 mb-2">
                      Documents Required
                    </h3>
                    <p className="text-sm text-amber-700 dark:text-amber-400">
                      This number requires identity verification. Please upload one of the following:
                    </p>
                    <ul className="mt-2 text-sm text-amber-700 dark:text-amber-400 list-disc list-inside">
                      <li>Company registration document</li>
                      <li>Passport or National ID</li>
                      <li>Proof of address (utility bill, bank statement)</li>
                    </ul>
                  </div>
                  
                  <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-8 text-center">
                    <input
                      type="file"
                      id="doc-upload"
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={handleDocumentUpload}
                      className="hidden"
                      disabled={uploadLoading}
                    />
                    <label
                      htmlFor="doc-upload"
                      className="cursor-pointer flex flex-col items-center"
                    >
                      {uploadLoading ? (
                        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mb-4"></div>
                      ) : (
                        <CloudArrowUpIcon className="h-10 w-10 text-gray-400 mb-4" />
                      )}
                      <span className="text-indigo-600 dark:text-indigo-400 font-medium">
                        Click to upload document
                      </span>
                      <span className="text-sm text-gray-500 mt-1">
                        PDF, JPG, PNG (max 10MB)
                      </span>
                    </label>
                  </div>
                  
                  {uploadedDocuments.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium text-gray-900 dark:text-white">Uploaded Documents:</h4>
                      {uploadedDocuments.map((doc, idx) => (
                        <div key={idx} className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                          <CheckCircleIcon className="h-5 w-5 text-green-600" />
                          <span className="text-sm text-green-700 dark:text-green-400">{doc}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  <Button
                    onClick={() => setCurrentStep('confirm')}
                    disabled={uploadedDocuments.length === 0}
                    className="w-full"
                  >
                    Continue to Confirmation
                  </Button>
                </div>
              )}
              
              {/* Confirmation */}
              {currentStep === 'confirm' && (
                <div className="space-y-6">
                  {/* Order Summary */}
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-6 space-y-4">
                    <h3 className="font-semibold text-gray-900 dark:text-white text-lg">Order Summary</h3>
                    
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-gray-600 dark:text-gray-400">Phone Number</span>
                        <span className="font-mono font-bold text-gray-900 dark:text-white">
                          {selectedNumber?.number_formatted}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600 dark:text-gray-400">Country</span>
                        <span className="text-gray-900 dark:text-white">{selectedCountry?.name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600 dark:text-gray-400">City</span>
                        <span className="text-gray-900 dark:text-white">{selectedDestination?.name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600 dark:text-gray-400">Type</span>
                        <span className="text-gray-900 dark:text-white capitalize">{selectedDestination?.type}</span>
                      </div>
                      <div className="border-t border-gray-200 dark:border-gray-700 pt-3 flex justify-between">
                        <span className="font-semibold text-gray-900 dark:text-white">Monthly Cost</span>
                        <span className="font-bold text-indigo-600 dark:text-indigo-400 text-lg">
                          €{selectedNumber?.monthly_fee}/month
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Business Info */}
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Business Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={businessName}
                        onChange={(e) => setBusinessName(e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                        placeholder="Your Company Name"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Purpose
                      </label>
                      <select
                        value={purpose}
                        onChange={(e) => setPurpose(e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                      >
                        <option value="AI Voice Agent">AI Voice Agent</option>
                        <option value="Customer Support">Customer Support</option>
                        <option value="Sales">Sales</option>
                        <option value="General Business">General Business</option>
                      </select>
                    </div>
                  </div>
                  
                  {/* Terms */}
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    By ordering this number, you agree to Zadarma's terms of service and understand that the monthly fee will be charged to your account.
                  </div>
                  
                  <Button
                    onClick={handleOrder}
                    disabled={loading || !businessName.trim()}
                    className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"
                  >
                    {loading ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                        Processing...
                      </>
                    ) : (
                      <>
                        <CheckCircleIcon className="h-5 w-5 mr-2" />
                        Order Number - €{selectedNumber?.monthly_fee}/month
                      </>
                    )}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
        
        {/* Footer Navigation */}
        {currentStep !== 'country' && currentStep !== 'confirm' && (
          <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <div className="flex items-center justify-between">
              <Button variant="outline" onClick={goBack}>
                <ArrowLeftIcon className="h-4 w-4 mr-2" />
                Back
              </Button>
              
              {/* Selection Summary */}
              <div className="text-sm text-gray-500 dark:text-gray-400">
                {selectedCountry && <span>{selectedCountry.name}</span>}
                {selectedDestination && <span> → {selectedDestination.name}</span>}
                {selectedNumber && <span className="font-mono"> → {selectedNumber.number_formatted}</span>}
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default RequestNumberModal;

