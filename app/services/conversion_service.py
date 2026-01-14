from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.conversion import ConversionModel, ConversionStatus, ConversionResponse
from typing import Optional
from datetime import datetime


class ConversionService:
    """Service for managing conversion database operations"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.db = database
        self.collection = database.conversions
    
    async def create_conversion(self, conversion: ConversionModel) -> ConversionModel:
        """
        Create a new conversion record
        
        Args:
            conversion: ConversionModel instance
            
        Returns:
            Created conversion document
        """
        conversion_dict = conversion.model_dump()
        conversion_dict['created_at'] = conversion.created_at.isoformat()
        
        await self.collection.insert_one(conversion_dict)
        return conversion
    
    async def get_conversion(self, conversion_id: str) -> Optional[ConversionModel]:
        """
        Get conversion by ID
        
        Args:
            conversion_id: Conversion ID
            
        Returns:
            ConversionModel if found, None otherwise
        """
        doc = await self.collection.find_one({"id": conversion_id})
        if doc:
            # Remove MongoDB _id field
            doc.pop('_id', None)
            # Parse datetime strings back to datetime objects
            if isinstance(doc.get('created_at'), str):
                doc['created_at'] = datetime.fromisoformat(doc['created_at'])
            if doc.get('completed_at') and isinstance(doc['completed_at'], str):
                doc['completed_at'] = datetime.fromisoformat(doc['completed_at'])
            return ConversionModel(**doc)
        return None
    
    async def update_status(
        self, 
        conversion_id: str, 
        status: ConversionStatus,
        error_message: Optional[str] = None,
        converted_file_path: Optional[str] = None,
        is_scanned_pdf: Optional[bool] = None
    ) -> bool:
        """
        Update conversion status
        
        Args:
            conversion_id: Conversion ID
            status: New status
            error_message: Optional error message
            converted_file_path: Optional path to converted file
            is_scanned_pdf: Optional flag for scanned PDF
            
        Returns:
            True if updated successfully
        """
        update_data = {
            "status": status.value
        }
        
        if error_message:
            update_data["error_message"] = error_message
        
        if converted_file_path:
            update_data["converted_file_path"] = converted_file_path
        
        if is_scanned_pdf is not None:
            update_data["is_scanned_pdf"] = is_scanned_pdf
        
        if status == ConversionStatus.COMPLETED:
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        result = await self.collection.update_one(
            {"id": conversion_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def delete_conversion(self, conversion_id: str) -> bool:
        """
        Delete conversion record
        
        Args:
            conversion_id: Conversion ID
            
        Returns:
            True if deleted successfully
        """
        result = await self.collection.delete_one({"id": conversion_id})
        return result.deleted_count > 0
    
    async def list_conversions(self, skip: int = 0, limit: int = 50) -> list[ConversionModel]:
        """
        List all conversions with pagination
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of ConversionModel instances
        """
        cursor = self.collection.find().skip(skip).limit(limit).sort("created_at", -1)
        conversions = []
        
        async for doc in cursor:
            doc.pop('_id', None)
            if isinstance(doc.get('created_at'), str):
                doc['created_at'] = datetime.fromisoformat(doc['created_at'])
            if doc.get('completed_at') and isinstance(doc['completed_at'], str):
                doc['completed_at'] = datetime.fromisoformat(doc['completed_at'])
            conversions.append(ConversionModel(**doc))
        
        return conversions
