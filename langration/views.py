from django.shortcuts import render
from django.http import JsonResponse
from langchain_core.messages import HumanMessage
from langration.src.graph.supervisor import supervisor

# Create your views here.
def home(request):
    return render(request, 'langration/home.html')

def execute_langration(request):
    # question = request.GET.get('question')
    question = """Document 만들어서 쓰는 부분인데 0.3 코드예요. 1.x로 바꿔 주세요.
    
    ```python
    from langchain.schema import Document
    from langchain.prompts import ChatPromptTemplate
    
    docs = [Document(page_content="LangChain 1.0 출시", metadata={"src": "news"})]
    prompt = ChatPromptTemplate.from_messages([("system", "요약가"), ("human", "{text}")])
    print(prompt.format_messages(text=docs[0].page_content))
    ```"""

    graph = supervisor()
    result = graph.invoke({ "messages": [HumanMessage(content=question)] })
    print(result)

    # return render(request, 'langration/home.html', { 'result': result })
    return JsonResponse(result)
